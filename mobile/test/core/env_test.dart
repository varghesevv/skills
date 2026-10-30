import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/app/build_error_app.dart';
import 'package:skills_app/core/env.dart';
import 'package:flutter/material.dart';

void main() {
  test('defaults to the demo flavor when none is given', () {
    expect(Env.flavor, 'demo');
  });

  group('problems', () {
    test('a configured build has none', () {
      expect(
        Env.problems(apiBase: 'https://api.test/api/v1', version: '1.2.3'),
        isEmpty,
      );
      expect(
        Env.problems(apiBase: 'https://api.test/api/v1', version: '1.2.3+45'),
        isEmpty,
      );
    });

    test('names a missing server address and a missing version', () {
      expect(Env.problems(apiBase: '', version: ''), [
        'API_BASE_URL',
        'APP_VERSION',
      ]);
    });

    test('a version that is not X.Y.Z is a problem', () {
      expect(
        Env.problems(apiBase: 'https://api.test/api/v1', version: 'latest'),
        ['APP_VERSION'],
      );
      expect(Env.problems(apiBase: 'https://api.test/api/v1', version: '1.2'), [
        'APP_VERSION',
      ]);
    });

    test('tests and debug runs without defines report both, so release builds can refuse them', () {
      expect(Env.problems(), ['API_BASE_URL', 'APP_VERSION']);
    });
  });

  testWidgets('the build error screen names the settings and no values', (
    tester,
  ) async {
    await tester.pumpWidget(
      const BuildErrorApp(problems: ['API_BASE_URL', 'APP_VERSION']),
    );
    expect(find.textContaining('API_BASE_URL, APP_VERSION'), findsOneWidget);
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
