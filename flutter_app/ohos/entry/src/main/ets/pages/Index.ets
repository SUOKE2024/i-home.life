import { FlutterPage } from '@ohos/flutter_ohos';
import common from '@ohos.app.ability.common';

let storage = LocalStorage.getShared();

const EVENT_BACK_PRESS = 'EVENT_BACK_PRESS';

/**
 * 索克家居主页面 — 全屏承载 Flutter 引擎视图。
 *
 * FlutterPage 渲染 flutter_app/lib/main.dart 的完整业务 UI；
 * 返回键事件经 eventHub 转发给 Flutter 侧处理路由栈。
 */
@Entry(storage)
@Component
struct Index {
  private context = getContext(this) as common.UIAbilityContext;
  @LocalStorageLink('viewId') viewId: string = '';

  build() {
    Column() {
      FlutterPage({ viewId: this.viewId })
    }
    .width('100%')
    .height('100%')
  }

  onBackPress(): boolean {
    this.context.eventHub.emit(EVENT_BACK_PRESS);
    return true;
  }
}
