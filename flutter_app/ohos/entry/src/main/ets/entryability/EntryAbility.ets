import UIAbility from '@ohos.app.ability.UIAbility';
import Want from '@ohos.app.ability.Want';
import window from '@ohos.window';
import AbilityConstant from '@ohos.app.ability.AbilityConstant';
import BusinessError from '@ohos.base';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    console.info('[ihome] EntryAbility onCreate');
  }

  onDestroy(): void {
    console.info('[ihome] EntryAbility onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    console.info('[ihome] EntryAbility onWindowStageCreate');
    windowStage.loadContent('pages/Index', (err: BusinessError.BusinessError, data: void) => {
      if (err.code) {
        console.error('[ihome] Failed to load content: ' + JSON.stringify(err));
        return;
      }
      console.info('[ihome] Content loaded successfully');
    });
  }

  onWindowStageDestroy(): void {
    console.info('[ihome] EntryAbility onWindowStageDestroy');
  }

  onForeground(): void {
    console.info('[ihome] EntryAbility onForeground');
  }

  onBackground(): void {
    console.info('[ihome] EntryAbility onBackground');
  }
}
