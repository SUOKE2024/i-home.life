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

  static bool get _isOHOS {
    try {
      return Platform.operatingSystem.toLowerCase() == 'ohos';
    } catch (_) {
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final Widget child = _isOHOS
        ? Image.network(
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
          )
        : CachedNetworkImage(
            imageUrl: imageUrl,
            width: width,
            height: height,
            fit: fit,
            placeholder: (context, url) =>
                placeholder?.call(context, url) ?? const SizedBox.shrink(),
            errorWidget: (context, url, error) =>
                errorWidget?.call(context, url, error) ?? const SizedBox.shrink(),
          );
    // CachedNetworkImage 不支持 semanticLabel 参数，用 Semantics 包裹提供无障碍标签
    if (semanticLabel == null || _isOHOS) return child;
    return Semantics(image: true, label: semanticLabel, child: child);
  }
}
