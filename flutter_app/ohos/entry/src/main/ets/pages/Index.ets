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
        Text('Flutter-OH 3.35.7-ohos-0.0.3')
          .fontSize(12)
          .fontColor('#5A5862')
          .margin({ top: 4 })
        Text('OpenHarmony API 23+ · HarmonyOS NEXT')
          .fontSize(10)
          .fontColor('#3A3842')
          .margin({ top: 2 })
      }
      .width('100%')
    }
    .height('100%')
    .backgroundColor('#12121D')
  }
}
