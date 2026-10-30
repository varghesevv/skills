import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/api/api_exception.dart';
import 'package:skills_app/core/api/parse.dart';
import 'package:skills_app/features/freelancer/data/freelancer_profile.dart';

Map<String, Object?> json({Object? rate = 45.5}) => {
  'id': 'f1',
  'full_name': 'Pat Example',
  'email': 'person@example.test',
  'mobile_number': '+971501234567',
  'whatsapp_availability': true,
  'nationality': null,
  'primary_language': null,
  'rate_per_hour': rate,
  'rate_currency': 'AED',
  'is_rate_negotiable': false,
};

void main() {
  FreelancerProfile parse(Map<String, Object?> data) =>
      parseResponse(data, FreelancerProfile.fromJson);

  test('reads a number, an integer, a numeric string and no rate', () {
    expect(parse(json(rate: 45.5)).ratePerHour, 45.5);
    expect(parse(json(rate: 45)).ratePerHour, 45.0);
    expect(parse(json(rate: '45.50')).ratePerHour, 45.5);
    expect(parse(json(rate: null)).ratePerHour, isNull);
  });

  test('a rate of any other shape is a bad response, not a crash', () {
    for (final bad in ['abc', true, <Object?>[], <String, Object?>{}]) {
      expect(
        () => parse(json(rate: bad)),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'bad_response'),
        ),
        reason: '$bad',
      );
    }
  });

  test('a missing required field is a bad response', () {
    final broken = json()..remove('is_rate_negotiable');
    expect(() => parse(broken), throwsA(isA<ApiException>()));
  });

  test('the update body sends nulls and a number', () {
    const update = FreelancerProfileUpdate(
      fullName: 'Pat',
      mobileNumber: '+971501234567',
      whatsappAvailability: false,
      nationality: null,
      primaryLanguage: null,
      ratePerHour: null,
      rateCurrency: null,
      isRateNegotiable: true,
    );
    final body = update.toJson();
    expect(body['rate_per_hour'], isNull);
    expect(body['nationality'], isNull);
    expect(
      body.keys,
      containsAll(['full_name', 'mobile_number', 'is_rate_negotiable']),
    );
  });
}
