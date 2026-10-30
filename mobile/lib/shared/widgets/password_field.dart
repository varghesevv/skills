import 'package:flutter/material.dart';

import 'app_text_field.dart';

/// A password field with a show/hide button (labelled for screen readers).
class PasswordField extends StatefulWidget {
  const PasswordField({
    super.key,
    required this.label,
    required this.controller,
    required this.showLabel,
    required this.hideLabel,
    this.error,
    this.hint,
    this.autofillHints = const [AutofillHints.password],
    this.textInputAction = TextInputAction.done,
    this.onSubmitted,
  });

  final String label;
  final TextEditingController controller;
  final String showLabel;
  final String hideLabel;
  final String? error;
  final String? hint;
  final Iterable<String> autofillHints;
  final TextInputAction textInputAction;
  final VoidCallback? onSubmitted;

  @override
  State<PasswordField> createState() => _PasswordFieldState();
}

class _PasswordFieldState extends State<PasswordField> {
  bool _visible = false;

  @override
  Widget build(BuildContext context) {
    return AppTextField(
      label: widget.label,
      controller: widget.controller,
      error: widget.error,
      hint: widget.hint,
      obscure: !_visible,
      autofillHints: widget.autofillHints,
      textInputAction: widget.textInputAction,
      onSubmitted: widget.onSubmitted,
      keyboardType: TextInputType.visiblePassword,
      suffix: IconButton(
        tooltip: _visible ? widget.hideLabel : widget.showLabel,
        icon: Icon(_visible ? Icons.visibility_off : Icons.visibility),
        onPressed: () => setState(() => _visible = !_visible),
      ),
    );
  }
}
