import 'dart:io' show Platform;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

/// 原生平台网络图片组件。
///
/// OHOS（Flutter-OH，Platform.operatingSystem == 'ohos'）上 cached_network_image
/// 未官方支持，降级为 Image.network（无磁盘缓存）；iOS/Android 保持磁盘缓存。
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

  static bool get _isOHOS {
    try {
      return Platform.operatingSystem.toLowerCase() == 'ohos';
    } catch (_) {
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isOHOS) {
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
    return CachedNetworkImage(
      imageUrl: imageUrl,
      width: width,
      height: height,
      fit: fit,
      placeholder: (context, url) =>
          placeholder?.call(context, url) ?? const SizedBox.shrink(),
      errorWidget: (context, url, error) =>
          errorWidget?.call(context, url, error) ?? const SizedBox.shrink(),
    );
  }
}
