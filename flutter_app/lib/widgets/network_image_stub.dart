import 'package:flutter/material.dart';

/// Web 平台网络图片组件（无磁盘缓存，直接 Image.network）。
class SuokeNetworkImage extends StatelessWidget {
  const SuokeNetworkImage({
    super.key,
    required this.imageUrl,
    this.fit,
    this.width,
    this.height,
    this.placeholder,
    this.errorWidget,
    this.semanticLabel,
  });

  final String imageUrl;
  final BoxFit? fit;
  final double? width;
  final double? height;
  final Widget Function(BuildContext context, String url)? placeholder;
  final Widget Function(BuildContext context, String url, Object error)?
      errorWidget;
  /// 无障碍：图片语义标签（读屏朗读，如「方案效果图」）
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    return Image.network(
      imageUrl,
      width: width,
      height: height,
      fit: fit,
      semanticLabel: semanticLabel,
      loadingBuilder: placeholder == null
          ? null
          : (context, child, progress) =>
              progress == null ? child : placeholder!(context, imageUrl),
      errorBuilder: errorWidget == null
          ? null
          : (context, error, stack) => errorWidget!(context, imageUrl, error),
    );
  }
}
