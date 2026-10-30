import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/auth/user_type.dart';

/// Checks what the app sends and reads against the committed API contract (`docs/openapi.json`,
/// kept current by `ci-backend`). When the backend changes an endpoint or a field the app uses,
/// this test fails in the same pull request instead of in a user's hands.
///
/// Add the endpoints and fields of every new feature here.
void main() {
  late Map<String, Object?> spec;
  late Map<String, Object?> schemas;

  setUpAll(() {
    final file = File('../docs/openapi.json');
    expect(
      file.existsSync(),
      isTrue,
      reason: 'docs/openapi.json is missing (run `make openapi`)',
    );
    spec = jsonDecode(file.readAsStringSync()) as Map<String, Object?>;
    schemas = (spec['components'] as Map)['schemas'] as Map<String, Object?>;
  });

  Map<String, Object?> operation(String method, String path) {
    final paths = spec['paths'] as Map;
    final item = paths['/api/v1$path'] as Map?;
    expect(item, isNotNull, reason: 'the API has no path $path');
    final op = item![method.toLowerCase()] as Map?;
    expect(op, isNotNull, reason: 'the API has no $method $path');
    return Map<String, Object?>.from(op!);
  }

  Map<String, Object?> schemaNamed(String name) {
    final schema = schemas[name];
    expect(schema, isNotNull, reason: 'the API has no schema $name');
    return Map<String, Object?>.from(schema! as Map);
  }

  Set<String> properties(String schema) =>
      (schemaNamed(schema)['properties'] as Map).keys.cast<String>().toSet();

  Set<String> required(String schema) =>
      ((schemaNamed(schema)['required'] as List?) ?? const [])
          .cast<String>()
          .toSet();

  String? refName(Object? node) =>
      node is Map ? (node[r'$ref'] as String?)?.split('/').last : null;

  String? requestSchema(String method, String path) {
    final body = operation(method, path)['requestBody'] as Map?;
    return refName(
      ((body?['content'] as Map?)?['application/json'] as Map?)?['schema'],
    );
  }

  String? responseSchema(String method, String path, String status) {
    final response =
        (operation(method, path)['responses'] as Map)[status] as Map?;
    expect(response, isNotNull, reason: '$method $path has no $status answer');
    return refName(
      ((response!['content'] as Map?)?['application/json'] as Map?)?['schema'],
    );
  }

  group('endpoints the app calls exist', () {
    const calls = {
      'GET /app/config': '200',
      'POST /auth/login': '200',
      'POST /auth/refresh': '200',
      'POST /auth/logout': '204',
      'POST /auth/forgot-password': '202',
      'POST /auth/register/freelancer': '201',
      'POST /auth/register/workhost': '201',
      'POST /auth/register/organisation': '201',
      'GET /me': '200',
    };
    calls.forEach((call, status) {
      test(call, () {
        final parts = call.split(' ');
        final op = operation(parts[0], parts[1]);
        expect(
          (op['responses'] as Map).containsKey(status),
          isTrue,
          reason: '$call should answer $status',
        );
      });
    });
  });

  group('requests the app sends', () {
    test('login body', () {
      expect(requestSchema('POST', '/auth/login'), 'LoginRequest');
      expect(required('LoginRequest'), {'email', 'password', 'user_type'});
    });

    test(
      'every user type the app sends is accepted, and the app has no admin',
      () {
        final userType =
            (schemaNamed('LoginRequest')['properties'] as Map)['user_type']
                as Map;
        final accepted = userType['enum'] as List;
        for (final type in UserType.values) {
          expect(accepted, contains(type.wire));
        }
        expect(UserType.values.map((t) => t.wire), isNot(contains('admin')));
      },
    );

    test('refresh and logout bodies', () {
      expect(requestSchema('POST', '/auth/refresh'), 'RefreshRequest');
      expect(required('RefreshRequest'), {'refresh_token'});
      expect(requestSchema('POST', '/auth/logout'), 'RefreshRequest');
    });

    test('forgot-password body', () {
      expect(required('ForgotPasswordRequest'), {'email', 'user_type'});
    });

    test('registration bodies carry the fields the forms send', () {
      expect(
        properties('FreelancerRegister'),
        containsAll([
          'full_name',
          'email',
          'mobile_number',
          'password',
          'nationality',
          'primary_language',
          'whatsapp_availability',
        ]),
      );
      expect(
        properties('WorkHostRegister'),
        containsAll(['full_name', 'email', 'mobile_number', 'password']),
      );
      expect(
        properties('OrganisationRegister'),
        containsAll(['org_name', 'email', 'mobile_number', 'password']),
      );
    });
  });

  group('answers the app reads', () {
    test('token answer', () {
      expect(responseSchema('POST', '/auth/login', '200'), 'TokenResponse');
      expect(responseSchema('POST', '/auth/refresh', '200'), 'TokenResponse');
      expect(
        required('TokenResponse'),
        containsAll(['access_token', 'refresh_token']),
      );
    });

    test('the account answer has the fields `Me` reads', () {
      expect(responseSchema('GET', '/me', '200'), 'MeResponse');
      expect(
        properties('MeResponse'),
        containsAll([
          'id',
          'user_type',
          'email',
          'mobile_number',
          'full_name',
          'org_name',
          'approval_status',
          'created_at',
        ]),
      );
    });

    test('registration answer has the approval status', () {
      expect(
        responseSchema('POST', '/auth/register/organisation', '201'),
        'RegisterResponse',
      );
      expect(properties('RegisterResponse'), contains('approval_status'));
    });

    test('app config has the words and versions', () {
      expect(responseSchema('GET', '/app/config', '200'), 'AppConfig');
      expect(required('AppConfig'), {'terminology', 'app'});
      expect(required('Terminology'), {'profile', 'terms'});
      expect(required('AppVersions'), {'min_version', 'latest_version'});
    });
  });
}
