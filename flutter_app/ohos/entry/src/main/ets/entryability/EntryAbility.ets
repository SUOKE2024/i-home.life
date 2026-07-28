import { FlutterAbility, FlutterEngine } from '@ohos/flutter_ohos';
import { GeneratedPluginRegistrant } from '../plugins/GeneratedPluginRegistrant';
import { AbilityConstant, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';

/**
 * 索克家居 i-home.life — HarmonyOS 入口 Ability
 *
 * 继承 FlutterAbility 托管 Flutter 引擎，Index.ets 通过 FlutterPage
 * 全屏承载 flutter_app 业务模块（与 Android/iOS 同一套 Dart 代码）。
 *
 * 构建前置（一次性）：在 flutter_app/ 下使用 Flutter-OH 工具链执行
 *   flutter build hap
 * 该命令会向本工程注入 flutter_ohos har 并重生成
 * plugins/GeneratedPluginRegistrant.ets（见该文件头部注释）。
 */
export default class EntryAbility extends FlutterAbility {
  configureFlutterEngine(flutterEngine: FlutterEngine): void {
    super.configureFlutterEngine(flutterEngine);
    GeneratedPluginRegistrant.registerWith(flutterEngine);
  }

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    hilog.info(0x0000, 'ihome', 'EntryAbility onCreate');
    return super.onCreate(want, launchParam);
  }

  onDestroy(): void {
    hilog.info(0x0000, 'ihome', 'EntryAbility onDestroy');
    return super.onDestroy();
  }

  onForeground(): void {
    hilog.info(0x0000, 'ihome', 'EntryAbility onForeground');
    super.onForeground();
  }

  onBackground(): void {
    hilog.info(0x0000, 'ihome', 'EntryAbility onBackground');
    super.onBackground();
  }
}
