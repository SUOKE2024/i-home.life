export default defineAppConfig({
  // 微信隐私协议：开启后调用隐私接口前必须取得用户同意。
  // 配套弹窗在 src/services/privacy-gate.ts 注册（wx.onNeedPrivacyAuthorization），
  // 由 src/app.tsx 启动时安装。
  // 需在小程序后台「设置 - 服务内容声明 - 用户隐私保护指引」同步勾选收集的信息类型。
  __usePrivacyCheck__: true,
  pages: [
    'pages/index/index',
    'pages/smart/index',
    'pages/care/index',
    'pages/project/index',
    'pages/mine/index',
    'pages/space-detail/index',
    'pages/project-detail/index',
    'pages/elderly-detail/index',
    'pages/ai-consult/index',
    'pages/agreement/index',
    'pages/demand/index'
  ],
  window: {
    backgroundTextStyle: 'dark',
    navigationBarBackgroundColor: '#F8F7F4',
    navigationBarTitleText: '索克家居',
    navigationBarTextStyle: 'black',
    backgroundColor: '#F8F7F4'
  },
  tabBar: {
    color: '#999999',
    selectedColor: '#8A6415',
    backgroundColor: '#FFFFFF',
    borderStyle: 'white',
    // 微信原生 tabBar 不支持 SVG：*.png（81×81，透明底）为实际渲染文件，
    // src/assets/tabbar/*.svg 保留为规范源（viewBox 0 0 24 24）。
    list: [
      {
        pagePath: 'pages/index/index',
        text: '首页',
        iconPath: 'assets/tabbar/home.png',
        selectedIconPath: 'assets/tabbar/home-selected.png'
      },
      {
        pagePath: 'pages/smart/index',
        text: '智控',
        iconPath: 'assets/tabbar/smart.png',
        selectedIconPath: 'assets/tabbar/smart-selected.png'
      },
      {
        pagePath: 'pages/care/index',
        text: '康养',
        iconPath: 'assets/tabbar/care.png',
        selectedIconPath: 'assets/tabbar/care-selected.png'
      },
      {
        pagePath: 'pages/project/index',
        text: '项目',
        iconPath: 'assets/tabbar/project.png',
        selectedIconPath: 'assets/tabbar/project-selected.png'
      },
      {
        pagePath: 'pages/mine/index',
        text: '我的',
        iconPath: 'assets/tabbar/mine.png',
        selectedIconPath: 'assets/tabbar/mine-selected.png'
      }
    ]
  }
})