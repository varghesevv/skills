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

  /// The JSON types a property accepts: `type`, or the `type`s inside `anyOf`.
  Set<String> typesOf(String schema, String field) {
    final property = Map<String, Object?>.from(
      (schemaNamed(schema)['properties'] as Map)[field] as Map,
    );
    final direct = property['type'];
    if (direct is String) return {direct};
    return {
      for (final option in (property['anyOf'] as List? ?? const []))
        (option as Map)['type'] as String,
    };
  }

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

  /// Every schema an answer may have: one `$ref`, or the `$ref`s inside `anyOf`.
  Set<String> responseSchemas(String method, String path, String status) {
    final response =
        (operation(method, path)['responses'] as Map)[status] as Map?;
    expect(response, isNotNull, reason: '$method $path has no $status answer');
    final schema =
        ((response!['content'] as Map?)?['application/json']
            as Map?)?['schema'];
    final names = <String>{};
    final direct = refName(schema);
    if (direct != null) names.add(direct);
    if (schema is Map) {
      for (final option in (schema['anyOf'] as List? ?? const [])) {
        final name = refName(option);
        if (name != null) names.add(name);
      }
    }
    return names;
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
      'GET /freelancers/me': '200',
      'PUT /freelancers/me': '200',
      'GET /labels': '200',
      'GET /freelancers/{freelancer_id}/ratings': '200',
      'PUT /freelancers/me/labels': '200',
      'GET /freelancers/me/unavailability': '200',
      'POST /freelancers/me/unavailability': '201',
      'PUT /freelancers/me/unavailability/{period_id}': '200',
      'DELETE /freelancers/me/unavailability/{period_id}': '204',
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
      // user_type became optional with the church trust model (ADR-0017): a request without
      // it logs in as a person. The older app still sends it, and the server still accepts it.
      expect(required('LoginRequest'), {'email', 'password'});
      expect(properties('LoginRequest'), contains('user_type'));
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
      expect(required('ForgotPasswordRequest'), {'email'});
      expect(properties('ForgotPasswordRequest'), contains('user_type'));
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
      // The answer is MeResponse for the older accounts the app uses today, or PersonMeResponse
      // for a person of the church trust model (the app moves to it in S2.8).
      expect(
        responseSchemas('GET', '/me', '200'),
        containsAll(['MeResponse', 'PersonMeResponse']),
      );
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

  group('freelancer profile', () {
    test('the update body has the fields the form sends', () {
      expect(requestSchema('PUT', '/freelancers/me'), 'FreelancerUpdate');
      expect(
        properties('FreelancerUpdate'),
        containsAll([
          'full_name',
          'mobile_number',
          'whatsapp_availability',
          'nationality',
          'primary_language',
          'rate_per_hour',
          'rate_currency',
          'is_rate_negotiable',
        ]),
      );
    });

    test('the profile answer has the fields the app reads', () {
      expect(responseSchema('GET', '/freelancers/me', '200'), 'FreelancerMe');
      expect(responseSchema('PUT', '/freelancers/me', '200'), 'FreelancerMe');
      expect(
        properties('FreelancerMe'),
        containsAll([
          'id',
          'full_name',
          'email',
          'mobile_number',
          'whatsapp_availability',
          'nationality',
          'primary_language',
          'rate_per_hour',
          'rate_currency',
          'is_rate_negotiable',
        ]),
      );
    });
  });

  group('freelancer profile field types', () {
    test('the answer has the types `FreelancerProfile.fromJson` casts to', () {
      const expected = {
        'id': {'string'},
        'full_name': {'string', 'null'},
        'email': {'string'},
        'mobile_number': {'string'},
        'whatsapp_availability': {'boolean'},
        'nationality': {'string', 'null'},
        'primary_language': {'string', 'null'},
        'rate_per_hour': {'number', 'null'},
        'rate_currency': {'string', 'null'},
        'is_rate_negotiable': {'boolean'},
      };
      expected.forEach((field, types) {
        expect(
          typesOf('FreelancerMe', field),
          types,
          reason: 'FreelancerMe.$field',
        );
      });
    });

    test('what the form sends is accepted by the update schema', () {
      // The app sends a JSON number for the rate, null for empty text and an empty rate.
      expect(
        typesOf('FreelancerUpdate', 'rate_per_hour'),
        containsAll(['number', 'null']),
      );
      for (final field in [
        'nationality',
        'primary_language',
        'rate_currency',
      ]) {
        expect(
          typesOf('FreelancerUpdate', field),
          containsAll(['string', 'null']),
          reason: field,
        );
      }
      expect(typesOf('FreelancerUpdate', 'mobile_number'), {'string'});
      expect(typesOf('FreelancerUpdate', 'whatsapp_availability'), {'boolean'});
      expect(typesOf('FreelancerUpdate', 'is_rate_negotiable'), {'boolean'});
    });
  });

  group('labels', () {
    test(
      'the catalogue and the choice have the fields and types the app reads',
      () {
        expect(typesOf('LabelOut', 'id'), {'string'});
        expect(typesOf('LabelOut', 'label_name'), {'string'});
        expect(typesOf('LabelOut', 'label_type'), {'string'});
        expect(typesOf('LabelOut', 'is_active'), {'boolean'});
        expect(required('FreelancerLabelOut'), contains('label'));
        expect(typesOf('FreelancerMe', 'labels'), {'array'});
      },
    );

    test('the replace body is {labels: [{label_id, level_label_id}]}', () {
      expect(requestSchema('PUT', '/freelancers/me/labels'), 'LabelsUpdate');
      expect(required('LabelsUpdate'), {'labels'});
      expect(
        properties('LabelSelection'),
        containsAll(['label_id', 'level_label_id']),
      );
      expect(typesOf('LabelSelection', 'label_id'), {'string'});
      expect(
        typesOf('LabelSelection', 'level_label_id'),
        containsAll(['string', 'null']),
      );
    });

    test('the label kinds the screen groups by exist', () {
      final parameters = (operation('GET', '/labels')['parameters'] as List)
          .cast<Map>();
      expect(parameters.map((p) => p['name']), contains('type'));
      final kinds =
          ((parameters.firstWhere((p) => p['name'] == 'type')['schema']
                      as Map)['anyOf']
                  as List)
              .cast<Map>()
              .expand((o) => (o['enum'] as List?) ?? const [])
              .toSet();
      expect(
        kinds,
        containsAll(['skill', 'language', 'timing', 'nativity', 'skill_level']),
      );
    });
  });

  group('unavailability', () {
    test('a period has the fields and types the app reads and sends', () {
      expect(typesOf('UnavailabilityOut', 'id'), {'string'});
      expect(typesOf('UnavailabilityOut', 'unavailable_from'), {'string'});
      expect(typesOf('UnavailabilityOut', 'unavailable_to'), {'string'});
      expect(required('UnavailabilityIn'), {
        'unavailable_from',
        'unavailable_to',
      });
      expect(
        requestSchema('POST', '/freelancers/me/unavailability'),
        'UnavailabilityIn',
      );
      expect(
        requestSchema('PUT', '/freelancers/me/unavailability/{period_id}'),
        'UnavailabilityIn',
      );
    });

    test(
      'the dates are date-times with a time zone, as the app sends them',
      () {
        final property =
            (schemaNamed('UnavailabilityIn')['properties']
                    as Map)['unavailable_from']
                as Map;
        expect(property['format'], 'date-time');
      },
    );
  });

  group('ratings received', () {
    test('the list is paged with page and page_size, at most 100', () {
      final parameters =
          (operation(
                    'GET',
                    '/freelancers/{freelancer_id}/ratings',
                  )['parameters']
                  as List)
              .cast<Map>();
      final byName = {for (final p in parameters) p['name'] as String: p};
      expect(byName.keys, containsAll(['page', 'page_size']));
      expect(
        (byName['page_size']!['schema'] as Map)['maximum'],
        greaterThanOrEqualTo(10),
      );
    });

    test('the page and a rating have the fields and types the app reads', () {
      expect(
        responseSchema('GET', '/freelancers/{freelancer_id}/ratings', '200'),
        'Page_PublicRating_',
      );
      expect(required('Page_PublicRating_'), {
        'items',
        'total',
        'page',
        'page_size',
      });
      expect(typesOf('Page_PublicRating_', 'items'), {'array'});
      for (final field in ['total', 'page', 'page_size']) {
        expect(typesOf('Page_PublicRating_', field), {
          'integer',
        }, reason: field);
      }
      expect(typesOf('PublicRating', 'rating'), {'integer'});
      expect(
        typesOf('PublicRating', 'comment'),
        containsAll(['string', 'null']),
      );
      expect(typesOf('PublicRating', 'rated_on'), {'string'});
    });

    test('a received rating never names the work host', () {
      expect(
        properties('PublicRating'),
        unorderedEquals(['rating', 'comment', 'rated_on']),
      );
    });
  });
}
