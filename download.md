把 `https://github.com/JuliusBrussee/caveman/tree/main/skills/caveman` 安装到本地给 VS Code 的 GitHub Copilot 用，**最推荐的方式是用官方提供的 `npx skills` 命令**，而不是自己手动下载。这个命令会自动把 caveman 技能安装到 VS Code Copilot 能识别的目录里，并生成/更新 `.github/copilot-instructions.md`，让 Copilot 每次聊天都自动走 caveman 风格。
---
## 一、推荐做法：用 `npx skills add` 一键安装
### 1. 前提条件
- 已安装：
  - Node.js（建议 18+）
  - VS Code
  - VS Code 里的 GitHub Copilot 扩展（已登录 GitHub 账号）
### 2. 在项目根目录执行安装命令
在你的项目根目录（也就是你打算用 Copilot 的那个仓库目录）打开终端，执行：
```bash
npx skills add JuliusBrussee/caveman -a github-copilot
```
说明：
- `JuliusBrussee/caveman`：就是你要安装的技能仓库（`skills/caveman` 这个目录是它里面的一个技能）。
- `-a github-copilot`：指定安装目标为 GitHub Copilot，这样 `npx skills` 会把技能放到 VS Code Copilot 能识别的路径，并自动生成/更新 `.github/copilot-instructions.md` 和 `AGENTS.md` 等文件。
- 默认是“项目级安装”（技能只在这个仓库生效），如果你希望全局所有项目都能用，可以加 `-g`：
  ```bash
  npx skills add JuliusBrussee/caveman -a github-copilot -g
  ```
  全局安装时，技能会放到类似 `~/.copilot/skills/` 的用户目录下，而不是项目里。
> Windows 如果遇到符号链接问题，可以加 `--copy` 改为复制而不是链接：  
> `npx skills add JuliusBrussee/caveman -a github-copilot --copy`
### 3. 确认安装结果
安装完成后，检查项目根目录：
1. 应该会出现（或被更新）这两个文件：
   - `.github/copilot-instructions.md`
   - `AGENTS.md`  
   这两个文件的内容是从 caveman 的 `rules/caveman-activate.md` 同步过来的，里面就是“像原始人一样说话，但技术内容不变”的那套指令，用来让 Copilot 自动走 caveman 风格。
2. VS Code 官方文档说明：  
   - 工作区根目录下的 `.github/copilot-instructions.md` 会被 VS Code **自动识别为“Always-on instructions”**，对该工作区里的所有 Copilot Chat 请求生效。
所以，只要你：
- 在这个项目目录下打开 VS Code，
- 使用 Copilot Chat（侧边栏聊天 / `Ctrl+Shift+P` → `GitHub Copilot: Chat`），
caveman 的指令就会自动注入，Copilot 默认就会按“极简、省 token、原始人风格”来回答你。
---
## 二、在 VS Code 里实际使用效果
### 1. Copilot Chat 里自动生效
- 打开 VS Code Copilot Chat（侧边栏 Chat 或 `Ctrl+Shift+P` → `GitHub Copilot: Chat`）。
- 直接问问题，比如：“这个接口怎么加认证？”
- 回复会比普通 Copilot 简洁很多，典型风格类似：
  - “New object ref each render. Inline object prop = new ref = re-render. Use useMemo.”
  - 中文场景下会变成类似：“新对象引用每次渲染。内联对象prop=新引用=重渲染。用useMemo。”
如果你没看到风格变化，可以：
1. 确认当前打开的工作区就是执行 `npx skills add` 的那个目录；
2. 重启 VS Code / 重新打开该工作区；
3. 在 Chat 里手动说一次：“talk like caveman” 或 “用 caveman 风格回复”，让它激活一次。
### 2. 关闭 / 恢复普通模式
caveman 的指令里给了关闭方式，你在聊天里说一句：
- “stop caveman”
- 或 “normal mode”
就可以恢复普通 Copilot 风格；想再开，再说 “talk like caveman” 即可。
---
## 三、如果你只想手动把 `skills/caveman` 拉下来（不推荐）
如果你只是想把那个目录下载下来自己研究，而不是作为 Copilot 技能使用，可以：
```bash
# 克隆整个仓库
git clone https://github.com/JuliusBrussee/caveman.git
# 然后 skills/caveman 就在本地了
cd caveman
ls skills/caveman
```
但这样**不会自动让 VS Code Copilot 使用它**，你还需要自己把 `skills/caveman/SKILL.md` 或 `rules/caveman-activate.md` 里的内容复制到 `.github/copilot-instructions.md`，或者按 VS Code 自定义指令的格式手动改写，这比直接用 `npx skills` 麻烦得多，而且以后更新也不方便。
---
## 四、小结（最简步骤）
1. 在你的项目根目录执行：
   ```bash
   npx skills add JuliusBrussee/caveman -a github-copilot
   ```
2. 确认项目里出现了 `.github/copilot-instructions.md`（和 `AGENTS.md`）。
3. 在 VS Code 中打开该项目，使用 Copilot Chat，caveman 风格会自动生效。
4. 想临时关闭，在聊天里说 “stop caveman”；想再开，说 “talk like caveman”。
这样就把 `https://github.com/JuliusBrussee/caveman/tree/main/skills/caveman` 正确安装到本地，并供 VS Code 的 GitHub Copilot 使用了。
