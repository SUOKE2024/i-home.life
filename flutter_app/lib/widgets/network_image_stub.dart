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
  });

  final String imageUrl;
  final BoxFit? fit;
  final double? width;
  final double? height;
  final Widget Function(BuildContext context, String url)? placeholder;
  final Widget Function(BuildContext context, String url, Object error)?
      errorWidget;

  @override
  Widget build(BuildContext context) {
    return Image.network(
      imageUrl,
      width: width,
      height: height,
      fit: fit,
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
