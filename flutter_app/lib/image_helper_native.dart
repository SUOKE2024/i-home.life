import 'dart:io';

import 'package:flutter/material.dart';

/// 原生平台：显示本地文件图片。
Widget buildLocalImage(String path,
    {double? width, double? height, BoxFit? fit, Widget? errorWidget}) {
  return Image.file(
    File(path),
    width: width,
    height: height,
    fit: fit,
    errorBuilder: errorWidget != null
        ? (BuildContext context, Object error, StackTrace? stackTrace) =>
            errorWidget
        : null,
  );
}
