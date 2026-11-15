import 'package:flutter/material.dart';

/// Page layout shared by the signed-out screens: scrollable, centred column that keeps the
/// keyboard from hiding the form and stays readable at large text sizes.
class AuthPage extends StatelessWidget {
  const AuthPage({
    super.key,
    required this.title,
    required this.children,
    this.showBack = true,
  });

  final String title;
  final List<Widget> children;
  final bool showBack;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title), automaticallyImplyLeading: showBack),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: ListView(
              padding: const EdgeInsets.all(16),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              children: [
                for (final child in children)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: child,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
