import 'package:flutter/material.dart';

/// A labelled text field with an optional hint and error message. The label is always visible
/// (also to screen readers); phone keyboards and autofill follow the field's meaning.
class AppTextField extends StatelessWidget {
  const AppTextField({
    super.key,
    required this.label,
    required this.controller,
    this.error,
    this.hint,
    this.keyboardType,
    this.autofillHints,
    this.textInputAction = TextInputAction.next,
    this.onSubmitted,
    this.obscure = false,
    this.suffix,
    this.enabled = true,
  });

  final String label;
  final TextEditingController controller;
  final String? error;
  final String? hint;
  final TextInputType? keyboardType;
  final Iterable<String>? autofillHints;
  final TextInputAction textInputAction;
  final VoidCallback? onSubmitted;
  final bool obscure;
  final Widget? suffix;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      enabled: enabled,
      obscureText: obscure,
      keyboardType: keyboardType,
      autofillHints: autofillHints,
      textInputAction: textInputAction,
      autocorrect: false,
      enableSuggestions: !obscure,
      onSubmitted: onSubmitted == null ? null : (_) => onSubmitted!(),
      decoration: InputDecoration(
        labelText: label,
        helperText: hint,
        helperMaxLines: 3,
        errorText: error,
        errorMaxLines: 3,
        suffixIcon: suffix,
        border: const OutlineInputBorder(),
      ),
    );
  }
}
