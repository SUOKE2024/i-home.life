import 'package:flutter/material.dart';

/// Web 平台：image_picker 返回 blob URL，使用 Image.network 显示。
Widget buildLocalImage(String path,
    {double? width, double? height, BoxFit? fit, Widget? errorWidget}) {
  return Image.network(
    path,
    width: width,
    height: height,
    fit: fit,
    errorBuilder: errorWidget != null
        ? (BuildContext context, Object error, StackTrace? stackTrace) =>
            errorWidget
        : null,
  );
}
