import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

/// 平台公开文档链接（与 webapp 公开路由一致，见 assets/guide + assets/legal）
class PublicDocLinks {
  static const String guide = 'https://i-home.life/guide';
  static const String privacy = 'https://i-home.life/legal/privacy';
  static const String terms = 'https://i-home.life/legal/terms';
  static const String beian = 'https://beian.miit.gov.cn/';
}

/// 打开外部链接；启动失败时降级为复制链接到剪贴板并提示。
/// 鸿蒙端若未接入 url_launcher 的 ohos 实现（openHarmony-tpc flutter_packages），
/// 走降级路径（复制链接），不影响主流程。
Future<void> openExternalUrl(BuildContext context, String url) async {
  try {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
      return;
    }
  } catch (_) {
    // 平台不支持，走复制降级
  }
  try {
    await Clipboard.setData(ClipboardData(text: url));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已复制链接：$url')),
      );
    }
  } catch (_) {}
}
