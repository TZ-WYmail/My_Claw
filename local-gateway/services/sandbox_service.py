"""
Docker 沙盒执行服务 — 容器调度 + 动态文件写入 + 输出回传
"""
from __future__ import annotations

import io
import logging
import os
import tarfile
import time
import uuid
from pathlib import Path
from typing import Optional

import docker
from docker.errors import DockerException, APIError, ImageNotFound

from config import (
    DOCKER_IMAGES,
    SANDBOX_MEMORY_LIMIT,
    SANDBOX_TIMEOUT,
    SANDBOX_WORKDIR,
    DOWNLOADS_DIR,
)

logger = logging.getLogger(__name__)


# ============================================================
# 沙盒执行
# ============================================================

async def execute_in_sandbox(
    tool_name: str,
    execution_command: str,
    setup_commands: Optional[list[str]] = None,
    dynamic_files: Optional[dict[str, str]] = None,
    input_files: Optional[list[str]] = None,
) -> dict:
    """
    在隔离 Docker 容器中执行任务。

    返回：同步结果或异步 job_id
    """
    # 1. 获取 Docker 客户端
    try:
        client = docker.from_env()
    except DockerException:
        return {
            "status": "error",
            "message": "Docker 未启动或未安装，请先启动 Docker 后重试",
        }

    # 2. 确定镜像
    image = DOCKER_IMAGES.get(tool_name)
    if not image:
        return {"status": "error", "message": f"未知工具: {tool_name}"}

    # 3. 拉取镜像（如不存在）
    try:
        client.images.get(image)
    except ImageNotFound:
        logger.info(f"拉取镜像 {image}...")
        try:
            client.images.pull(image)
        except Exception as e:
            return {"status": "error", "message": f"拉取镜像失败: {e}"}

    # 4. 准备容器配置
    container_name = f"lcc_{tool_name}_{uuid.uuid4().hex[:8]}"
    volumes: dict[str, dict] = {}

    # 挂载输入文件
    if input_files:
        for host_path in input_files:
            p = Path(host_path)
            if p.exists():
                volumes[str(p.parent)] = {"bind": f"{SANDBOX_WORKDIR}", "mode": "rw"}
                break  # 只挂载第一个父目录即可

    # 5. 创建并启动容器
    try:
        container = client.containers.create(
            image=image,
            name=container_name,
            working_dir=SANDBOX_WORKDIR,
            command="tail -f /dev/null",  # 保持容器运行
            mem_limit=SANDBOX_MEMORY_LIMIT,
            volumes=volumes,
            detach=True,
        )
        container.start()
    except APIError as e:
        return {"status": "error", "message": f"容器创建失败: {e}"}

    start_time = time.time()

    try:
        # 6. 动态写入文件
        if dynamic_files:
            for fname, content in dynamic_files.items():
                _put_file(container, f"{SANDBOX_WORKDIR}/{fname}", content)

        # 7. 执行 setup 命令
        if setup_commands:
            for cmd in setup_commands:
                logger.info(f"setup: {cmd}")
                exit_code, output = container.exec_run(
                    cmd,
                    workdir=SANDBOX_WORKDIR,
                    demux=True,
                )
                if exit_code != 0:
                    stderr_bytes = output[1] if output[1] else b""
                    # 不因 setup 警告失败
                    logger.warning(f"setup 命令退出码 {exit_code}: {stderr_bytes.decode(errors='replace')}")

        # 8. 执行主命令
        logger.info(f"exec: {execution_command}")
        exit_code, output = container.exec_run(
            execution_command,
            workdir=SANDBOX_WORKDIR,
            demux=True,
        )

        stdout_bytes = output[0] if output[0] else b""
        stderr_bytes = output[1] if output[1] else b""

        duration = round(time.time() - start_time, 1)

        # 9. 收集输出文件
        output_files = _list_workspace_files(container)
        copied_files = _copy_output_files(container, output_files)

        result = {
            "status": "success" if exit_code == 0 else "error",
            "exit_code": exit_code,
            "stdout": stdout_bytes.decode(errors="replace")[:10000],
            "stderr": stderr_bytes.decode(errors="replace")[:5000],
            "output_files": output_files,
            "copied_to": copied_files,
            "duration_seconds": duration,
            "message": "沙盒执行完成" if exit_code == 0 else f"执行失败 (exit code: {exit_code})",
        }

        # 检查是否超时
        if duration >= SANDBOX_TIMEOUT - 5:
            result["message"] += " (接近超时)"

        return result

    except Exception as e:
        logger.exception("沙盒执行异常")
        return {
            "status": "error",
            "message": f"沙盒执行异常: {e}",
            "duration_seconds": round(time.time() - start_time, 1),
        }

    finally:
        # 10. 清理容器
        try:
            container.stop(timeout=5)
            container.remove(force=True)
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


# ============================================================
# 容器文件操作
# ============================================================

def _put_file(container, container_path: str, content: str):
    """向容器写入文件"""
    filename = Path(container_path).name
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        info = tarfile.TarInfo(name=filename)
        content_bytes = content.encode("utf-8")
        info.size = len(content_bytes)
        tar.addfile(info, io.BytesIO(content_bytes))
    tar_stream.seek(0)
    container.put_archive(str(Path(container_path).parent), tar_stream)


def _list_workspace_files(container) -> list[str]:
    """列出容器 /workspace 下的文件"""
    try:
        exit_code, output = container.exec_run(
            f"find {SANDBOX_WORKDIR} -maxdepth 1 -type f",
            workdir=SANDBOX_WORKDIR,
            demux=True,
        )
        if exit_code == 0 and output[0]:
            files = output[0].decode(errors="replace").strip().split("\n")
            return [f for f in files if f.strip()]
    except Exception:
        pass
    return []


def _copy_output_files(container, output_files: list[str]) -> list[str]:
    """将输出文件复制回宿主机 downloads 目录"""
    copied = []
    for container_path in output_files:
        try:
            bits, stat = container.get_archive(container_path)
            filename = Path(container_path).name
            dest = DOWNLOADS_DIR / "misc" / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in bits:
                    f.write(chunk)
            copied.append(str(dest))
        except Exception as e:
            logger.warning(f"复制输出文件失败 {container_path}: {e}")
    return copied
