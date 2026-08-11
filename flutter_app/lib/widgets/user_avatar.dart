import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../image_helper.dart';
import '../services/avatar_controller.dart';
import '../theme/suoke_theme.dart';

/// 用户头像展示（读取 AvatarController，跨页面共享同一头像）。
///
/// 优先级：相册自定义 > 手绘宫格选择 > 本次启动随机。
class UserAvatar extends StatelessWidget {
  const UserAvatar({super.key, this.size = 36, this.showBorder = true});

  final double size;
  final bool showBorder;

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<AvatarController>();
    final theme = Theme.of(context);
    final borderColor =
        showBorder ? theme.colorScheme.outlineVariant : Colors.transparent;

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: borderColor, width: 1.5),
      ),
      child: ClipOval(
        child: controller.customPath != null
            ? buildLocalImage(
                controller.customPath!,
                width: size,
                height: size,
                fit: BoxFit.cover,
                errorWidget: _fallback(context),
              )
            : Image.asset(
                controller.assetPath,
                width: size,
                height: size,
                fit: BoxFit.cover,
                errorBuilder: (_, _, _) => _fallback(context),
              ),
      ),
    );
  }

  Widget _fallback(BuildContext context) {
    return Container(
      color: SuokeDesignTokens.accent.withValues(alpha: 0.2),
      child: Icon(Icons.person, size: size * 0.55, color: SuokeDesignTokens.accent),
    );
  }
}

/// 弹出头像选择器：手绘头像宫格 + 相册自定义 + 随机换一个。
Future<void> showUserAvatarPicker(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (ctx) {
      final controller = ctx.watch<AvatarController>();
      final text = SuokeDesignTokens.text(ctx);
      final sub = SuokeDesignTokens.textSub(ctx);

      return SafeArea(
        child: SizedBox(
          height: MediaQuery.of(ctx).size.height * 0.72,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 顶部：当前头像 + 标题 + 操作
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
                child: Row(
                  children: [
                    const UserAvatar(size: 48),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('选择头像',
                              style: TextStyle(
                                  color: text,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700)),
                          const SizedBox(height: 2),
                          Text('从相册上传，或挑一张手绘头像',
                              style: TextStyle(color: sub, fontSize: 12)),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: '关闭',
                      icon: const Icon(Icons.close),
                      color: sub,
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ],
                ),
              ),
              // 操作按钮
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
                child: Row(
                  children: [
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: () => _pickFromGallery(ctx, controller),
                        icon: const Icon(Icons.photo_library, size: 18),
                        label: const Text('从相册选择'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () {
                          controller.randomize();
                          ScaffoldMessenger.of(ctx).showSnackBar(
                            SnackBar(
                                content: Text('已为你换一张头像',
                                    style:
                                        TextStyle(color: SuokeDesignTokens.text(ctx)))),
                          );
                        },
                        icon: const Icon(Icons.refresh, size: 18),
                        label: const Text('随机换一个'),
                      ),
                    ),
                  ],
                ),
              ),
              // 手绘头像宫格
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 14, 20, 6),
                child: Text('手绘头像 · 共 ${AvatarController.assetCount} 张',
                    style: TextStyle(color: sub, fontSize: 12, fontWeight: FontWeight.w600)),
              ),
              Expanded(
                child: GridView.builder(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 4,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                  ),
                  itemCount: AvatarController.assetCount,
                  itemBuilder: (ctx, i) {
                    final index = i + 1;
                    final selected =
                        controller.customPath == null &&
                        controller.chosenIndex == index;
                    return Semantics(
                      button: true,
                      label: '手绘头像 $index',
                      selected: selected,
                      child: GestureDetector(
                        onTap: () {
                          controller.setChosenIndex(index);
                          Navigator.pop(ctx);
                        },
                        child: Container(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: selected
                                  ? SuokeDesignTokens.accent
                                  : SuokeDesignTokens.borderClr(ctx),
                              width: selected ? 2.5 : 1,
                            ),
                          ),
                          padding: EdgeInsets.all(selected ? 2 : 3),
                          child: ClipOval(
                            child: Image.asset(
                              'assets/images/avatars/hand-drawn-profiles/$index.webp',
                              fit: BoxFit.cover,
                              errorBuilder: (_, _, _) => Container(
                                color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                              ),
                            ),
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}

Future<void> _pickFromGallery(BuildContext ctx, AvatarController controller) async {
  final messenger = ScaffoldMessenger.of(ctx);
  try {
    final picked = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      imageQuality: 80,
      maxWidth: 512,
      maxHeight: 512,
    );
    if (picked == null) return;
    await controller.setCustomPath(picked.path);
    if (ctx.mounted) {
      Navigator.pop(ctx);
      messenger.showSnackBar(
        SnackBar(
          content: Text('头像已更换',
              style: TextStyle(color: SuokeDesignTokens.text(ctx))),
        ),
      );
    }
  } catch (e) {
    debugPrint('从相册选择头像失败: $e');
  }
}
