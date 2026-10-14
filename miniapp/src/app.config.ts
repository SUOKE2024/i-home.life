export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/smart/index',
    'pages/care/index',
    'pages/project/index',
    'pages/mine/index',
    'pages/space-detail/index',
    'pages/project-detail/index',
    'pages/elderly-detail/index',
    'pages/ai-consult/index'
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
    list: [
      {
        pagePath: 'pages/index/index',
        text: '首页',
        iconPath: 'assets/tabbar/home.svg',
        selectedIconPath: 'assets/tabbar/home-selected.svg'
      },
      {
        pagePath: 'pages/smart/index',
        text: '智控',
        iconPath: 'assets/tabbar/smart.svg',
        selectedIconPath: 'assets/tabbar/smart-selected.svg'
      },
      {
        pagePath: 'pages/care/index',
        text: '康养',
        iconPath: 'assets/tabbar/care.svg',
        selectedIconPath: 'assets/tabbar/care-selected.svg'
      },
      {
        pagePath: 'pages/project/index',
        text: '项目',
        iconPath: 'assets/tabbar/project.svg',
        selectedIconPath: 'assets/tabbar/project-selected.svg'
      },
      {
        pagePath: 'pages/mine/index',
        text: '我的',
        iconPath: 'assets/tabbar/mine.svg',
        selectedIconPath: 'assets/tabbar/mine-selected.svg'
      }
    ]
  }
})