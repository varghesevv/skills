import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/env.dart';

void main() {
  test('defaults to the demo flavor when none is given', () {
    expect(Env.flavor, 'demo');
  });
}
