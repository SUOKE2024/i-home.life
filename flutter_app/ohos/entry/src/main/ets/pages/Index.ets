@Entry
@Component
struct Index {
  @State message: string = '索克家居 i-home.life';

  build() {
    Row() {
      Column() {
        Text(this.message)
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
          .margin({ top: 20 })
        Text('HUAWEI MatePad Pro')
          .fontSize(16)
          .fontColor('#8A8894')
          .margin({ top: 8 })
      }
      .width('100%')
    }
    .height('100%')
    .backgroundColor('#12121D')
  }
}
