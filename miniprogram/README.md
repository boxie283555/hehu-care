# 禾护 · 微信小程序开发版

这是微信原生小程序工程，不是网页套壳。家长使用小程序，医护继续使用电脑浏览器后台；两端共享同一数据库。

## 目前可体验

- 指定问卷入口 → 手机验证码登录 → 选择 / 建立患儿 → 填写 → 提交结果。
- 初次综合、营养随访、过敏症状三类问卷，服务端草稿保存与恢复。
- 健康空间：历史问卷、生长记录、测量录入、医护评估与计划、随访任务、留言回复。
- 登录失效后重新登录，保留待填问卷；多患儿须明确选择。

验证码仍为演示模式，直接显示在页面。没有接入微信一键手机号、真实短信、订阅消息或正式小程序码。小程序使用服务端签发的短期Bearer会话，不依赖网页Cookie。

## 没有 AppID 怎么演示

1. 先按仓库根目录README配置PostgreSQL，再在电脑上启动最新后台。Windows双击仓库根目录的 `start-windows.cmd`，会自动准备Python。
2. 安装并打开[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)，用微信登录工具。
3. 选择导入项目，目录选择仓库中的 **`miniprogram` 文件夹**，不是整个仓库，也不是 `web`。
4. 使用测试号/无AppID的本地开发模式。工程中的 `touristappid` 是开发占位值，不是真实已注册AppID；工具版本若要求先申请测试号，按工具提供的测试号入口操作。
5. 在本地设置中开启“不校验合法域名、web-view业务域名、TLS版本以及HTTPS证书”。这仅用于开发调试，不能用于正式上线。
6. 默认 `config.js` 指向 `http://127.0.0.1:8765`，开发者工具与后台位于同一电脑时无需修改。
7. 选择预设编译条件“营养随访问卷扫码入口”或“首次综合评估扫码入口”，点击编译。也可以自定义入口：

   - 启动页面：`pages/entry/index`
   - 参数：`questionnaire=nutrition` 或 `scene=nutrition`
   - 可用值：`initial`、`nutrition`、`symptoms`

8. 使用 `13800138000` 获取开发验证码，进入示例患儿；其他手机号可演示全新建档。
9. 手机提交的数据会立即写入后台，电脑医护账号 `doctor / Care2026!` 可查看。

**没有注册AppID时，主要演示方式是开发者工具模拟器。** 不能把现有H5二维码当作小程序码，也不能保证游客项目支持微信真机预览。真机预览/体验版需要工具支持的有效测试号或注册AppID及相应权限。

## 后续手机真机与公网

- 本地真机调试时，将 `config.js` 中 apiBase 改为手机可以访问的服务器地址。`127.0.0.1` 在手机上指手机自身，不是后台电脑；开发工具的模拟器配置不自动适用于手机。
- 注册后，在 `project.config.json` 中填写真实AppID，设置体验成员，再通过开发工具上传/预览。
- 正式公网部署使用HTTPS域名，并配置微信后台的request合法域名。项目部署在域名根路径。
- 正式小程序码指向 `pages/entry/index`，scene为 `initial` / `nutrition` / `symptoms`。需后端使用真实AppID与AppSecret调用微信生成接口；当前未实现该外部接口，也未生成正式小程序码。
- AppSecret只能保存在服务器，不能放进本工程、二维码或GitHub。
- 之后补充真实短信、隐私声明与平台要求的隐私授权流程、医护正式账号权限及上线审核。当前只使用演示资料。

## 工程结构

- `app.json`：页面路由；`project.config.json`：开发者工具配置与编译条件。
- `pages/entry`：扫码入口及监护人登录。
- `pages/children`、`pages/child-new`：选择及建立患儿。
- `pages/questionnaire`、`pages/result`：问卷与提交结果。
- `pages/health`：健康记录、计划、随访和沟通。
- `utils/api.js`：微信网络请求与登录失效处理。
- `utils/session.js`：指定问卷状态及白名单校验。

## 验证范围

仓库根目录运行：

```sh
python -m unittest discover -s tests -v
node tests/miniprogram.cjs
```

测试使用真实HTTP后台和隔离的PostgreSQL schema，模拟wx网络/存储接口，验证页面控制逻辑及接口合同。它不能替代微信开发者工具编译、原生组件渲染或iPhone/Android真机验证。当前开发环境未安装微信开发者工具，尚未完成这些平台内验证。
