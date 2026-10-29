import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/validation/validators.dart';

void main() {
  group('email', () {
    test(
      'accepts a normal address',
      () => expect(requiredEmail(' person@example.test '), isNull),
    );
    test(
      'asks for a value',
      () => expect(requiredEmail('  '), 'validation.required'),
    );
    test('rejects text that is not an address', () {
      expect(requiredEmail('person'), 'validation.email');
      expect(requiredEmail('a@b'), 'validation.email');
      expect(requiredEmail('a b@c.de'), 'validation.email');
    });
    test(
      'rejects a very long address',
      () => expect(requiredEmail('${'a' * 250}@b.de'), 'validation.email'),
    );
  });

  group('password', () {
    test('login only needs a value', () {
      expect(requiredPassword(''), 'validation.required');
      expect(requiredPassword('x'), isNull);
      expect(requiredPassword('x' * 1025), 'validation.tooLong');
    });
    test('a new password has 10 to 128 characters', () {
      expect(newPassword('x' * 9), 'validation.passwordShort');
      expect(newPassword('x' * 10), isNull);
      expect(newPassword('x' * 128), isNull);
      expect(newPassword('x' * 129), 'validation.passwordLong');
    });
  });

  group('names', () {
    test('full name 2 to 200 characters after trimming', () {
      expect(fullName(' a '), 'validation.fullName');
      expect(fullName('Al'), isNull);
      expect(fullName('a' * 201), 'validation.fullName');
    });
    test('organisation name 2 to 200 characters', () {
      expect(orgName('a'), 'validation.orgName');
      expect(orgName('Ab'), isNull);
    });
    test('optional text at most 100 characters', () {
      expect(optionalText(''), isNull);
      expect(optionalText('a' * 101), 'validation.tooLong');
    });
  });

  group('mobile', () {
    test(
      'accepts 7 to 15 digits with optional +, ignoring spaces and dashes',
      () {
        expect(mobile('+971 50-123 4567'), isNull);
        expect(mobile('5551234'), isNull);
        expect(normaliseMobile('+971 50-123 4567'), '+971501234567');
      },
    );
    test('rejects letters, too short and too long', () {
      expect(mobile('12345'), 'validation.mobile');
      expect(mobile('1234567890123456'), 'validation.mobile');
      expect(mobile('call me'), 'validation.mobile');
      expect(mobile('++971501234567'), 'validation.mobile');
    });
  });

  group('forms', () {
    test('login lists only the failed fields', () {
      final failed = validateLogin(email: 'x', password: '');
      expect(failed.keys, ['email', 'password']);
      expect(failed['email'], 'validation.email');
      expect(failed['password'], 'validation.required');
      expect(validateLogin(email: 'a@b.de', password: 'x'), isEmpty);
    });

    test(
      'registration uses org_name for organisations and full_name for people',
      () {
        final org = validateRegistration(
          type: 'organisation',
          name: '',
          email: 'a@b.de',
          mobileNumber: '5551234',
          password: 'x' * 10,
        );
        expect(org.keys, ['org_name']);
        final host = validateRegistration(
          type: 'workhost',
          name: '',
          email: 'a@b.de',
          mobileNumber: '5551234',
          password: 'x' * 10,
        );
        expect(host.keys, ['full_name']);
      },
    );

    test('only freelancers have the optional fields checked', () {
      final long = 'a' * 101;
      expect(
        validateRegistration(
          type: 'workhost',
          name: 'Al',
          email: 'a@b.de',
          mobileNumber: '5551234',
          password: 'x' * 10,
          nationality: long,
        ),
        isEmpty,
      );
      expect(
        validateRegistration(
          type: 'freelancer',
          name: 'Al',
          email: 'a@b.de',
          mobileNumber: '5551234',
          password: 'x' * 10,
          nationality: long,
        ).keys,
        ['nationality'],
      );
    });
  });
}
