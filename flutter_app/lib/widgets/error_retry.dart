import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';

class ErrorRetryWidget extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const ErrorRetryWidget({
    super.key,
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '错误：$message',
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.error_outline,
                size: 48,
                color: SuokeDesignTokens.danger,
              ),
              const SizedBox(height: 16),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: SuokeDesignTokens.textSecondary),
              ),
              const SizedBox(height: 20),
              Semantics(
                label: '重试',
                button: true,
                child: OutlinedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh, size: 18),
                  label: const Text('重试'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: SuokeDesignTokens.accent,
                    side: const BorderSide(color: SuokeDesignTokens.accent),
                    padding:
                        const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
