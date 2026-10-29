import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/app.dart';

void main() {
  testWidgets('starts and shows the start screen', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: SkillsApp()));
    await tester.pumpAndSettle();
    expect(find.text('Starting'), findsOneWidget);
  });

  testWidgets('keeps tap targets at 48 dp and has labels', (tester) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(const ProviderScope(child: SkillsApp()));
    await tester.pumpAndSettle();
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    handle.dispose();
  });

  testWidgets('renders at text scale 2.0 without overflow', (tester) async {
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(tester.platformDispatcher.clearAllTestValues);
    await tester.pumpWidget(const ProviderScope(child: SkillsApp()));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
