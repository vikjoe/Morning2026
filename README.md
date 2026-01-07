# Morning2026

这个项目用于每天早上 9:00 (北京时间) 给你的微信推送一条“早上好”的消息。

## 如何使用 (How to use)

由于微信不再支持个人号直接通过 API 发送消息，本项目使用 [PushPlus](https://www.pushplus.plus/) 服务来实现消息推送。这是一种安全、简单且免费的方式。

### 第一步：获取 Token
1. 访问 [PushPlus 官网](https://www.pushplus.plus/) 并使用微信扫码登录。
2. 登录成功后，你会看到你的 **Token**。复制这个字符串，不要告诉任何人。

### 第二步：部署到 GitHub
1. 在 GitHub 上创建一个新的仓库，建议命名为 `Morning2026`。
2. 将本项目代码推送到该仓库。

### 第三步：配置 GitHub Secrets
为了保护你的 Token 安全，**不要**将其直接写在代码里。我们需要使用 GitHub Secrets。

1. 打开你新建的 GitHub 仓库页面。
2. 点击上方的 **Settings** (设置)。
3. 在左侧菜单中找到 **Secrets and variables**，点击展开，然后选择 **Actions**。
4. 点击 **New repository secret** (新建仓库密钥)。
5. **Name** (名称) 填写: `PUSHPLUS_TOKEN`
6. **Secret** (内容) 填写: 第一步中你获取到的 PushPlus Token。
7. 点击 **Add secret** 保存。

### 第四步：测试
配置完成后，GitHub Actions 会在每天早上 9:00 自动运行。
你也可以手动测试：
1. 点击仓库上方的 **Actions** 标签。
2. 在左侧选择 "Morning Greeting" 工作流。
3. 点击右侧的 **Run workflow** 按钮进行手动触发。
4. 检查你的微信是否收到了消息。

## 目录结构
- `main.py`: 主程序代码。
- `.github/workflows/daily.yml`: 定时任务配置。
- `requirements.txt`: 依赖库列表。
