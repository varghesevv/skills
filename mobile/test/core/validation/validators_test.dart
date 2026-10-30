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

  group('freelancer profile', () {
    FieldKeys check({
      String name = 'Pat Example',
      String mobileNumber = '+971501234567',
      String nationality = '',
      String language = '',
      String rate = '',
      String currency = '',
    }) => validateFreelancerProfile(
      fullNameValue: name,
      mobileNumber: mobileNumber,
      nationality: nationality,
      primaryLanguage: language,
      ratePerHour: rate,
      rateCurrency: currency,
    );

    test('a profile without a rate is valid', () => expect(check(), isEmpty));

    test('rates have up to 8 digits and 2 decimals', () {
      for (final good in ['45', '45.5', '45.50', '12345678', '0.99', ' 45 ']) {
        expect(rate(good), isNull, reason: good);
      }
      for (final bad in ['45.555', '123456789', '-5', '4,5', 'abc', '.5']) {
        expect(rate(bad), 'validation.rate', reason: bad);
      }
    });

    test('currency is three letters in any case', () {
      expect(currency('aed'), isNull);
      expect(currency(' USD '), isNull);
      expect(normaliseCurrency(' usd '), 'USD');
      expect(currency('US'), 'validation.currency');
      expect(currency('USDX'), 'validation.currency');
      expect(currency('U5D'), 'validation.currency');
    });

    test('a rate and a currency go together', () {
      expect(check(rate: '30', currency: 'AED'), isEmpty);
      expect(check(rate: '30')['rate_currency'], 'validation.rateTogether');
      expect(
        check(currency: 'AED')['rate_per_hour'],
        'validation.rateTogether',
      );
    });

    test('the other fields use the same rules as registration', () {
      final failed = check(
        name: 'P',
        mobileNumber: '12',
        nationality: 'a' * 101,
        language: 'b' * 101,
      );
      expect(failed.keys.toSet(), {
        'full_name',
        'mobile_number',
        'nationality',
        'primary_language',
      });
    });
  });
}
