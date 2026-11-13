import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import 'person_router_paths.dart';

/// The token is the last part of a pasted link, or the whole text when only the token is given.
String? vouchTokenFrom(String pasted) {
  final trimmed = pasted.trim().split('?').first.split('#').first;
  final last = trimmed.split('/').where((p) => p.isNotEmpty).lastOrNull;
  return last == null || last.length < 10 ? null : last;
}

/// Asks for a pasted vouch link and opens it. (A tap on a link in another app needs app links,
/// which come with the release setup; until then people paste it.)
Future<void> askForVouchLink(BuildContext context) async {
  final link = await showDialog<String>(
    context: context,
    builder: (context) => const _PasteDialog(),
  );
  final token = vouchTokenFrom(link ?? '');
  if (token != null && context.mounted) {
    context.push('$vouchLinkPrefix$token');
  }
}

/// Owns its controller, so the controller lives exactly as long as the dialog (also while it
/// animates away).
class _PasteDialog extends ConsumerStatefulWidget {
  const _PasteDialog();

  @override
  ConsumerState<_PasteDialog> createState() => _PasteDialogState();
}

class _PasteDialogState extends ConsumerState<_PasteDialog> {
  final _link = TextEditingController();

  @override
  void dispose() {
    _link.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = ref.watch(appTextProvider);
    return AlertDialog(
      title: Text(text('vouch.paste.title')),
      content: TextField(
        key: const Key('vouch-link-field'),
        controller: _link,
        autofocus: true,
        autocorrect: false,
        decoration: InputDecoration(labelText: text('vouch.paste.hint')),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(text('vouch.paste.cancel')),
        ),
        FilledButton(
          key: const Key('vouch-link-open'),
          onPressed: () => Navigator.of(context).pop(_link.text),
          child: Text(text('vouch.paste.go')),
        ),
      ],
    );
  }
}
