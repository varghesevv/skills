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

  /// The schemas a property refers to (directly, or inside `anyOf` for an optional one).
  Set<String> refsOf(String schema, String field) {
    final property = Map<String, Object?>.from(
      (schemaNamed(schema)['properties'] as Map)[field] as Map,
    );
    final candidates = [
      property,
      for (final option in (property['anyOf'] as List?) ?? const [])
        Map<String, Object?>.from(option as Map),
    ];
    return {
      for (final c in candidates)
        if (c[r'$ref'] != null) (c[r'$ref'] as String).split('/').last,
    };
  }

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
      // The church trust model (docs/specification/04-api.md).
      'POST /auth/signup': '201',
      'GET /churches': '200',
      'GET /churches/{church_id}/home-groups': '200',
      'POST /group-invitations/lookup': '200',
      'PUT /me/application': '200',
      'DELETE /me': '204',
      // Vouching, notifications and the screens of a leader.
      'POST /me/apply-provider': '200',
      'GET /me/vouch-link': '200',
      'POST /me/vouch-link': '201',
      'GET /me/vouches': '200',
      'GET /me/vouches-given': '200',
      'POST /vouch-links/lookup': '200',
      'POST /vouch-links/vouch': '201',
      'DELETE /vouches/{vouch_id}': '204',
      'GET /me/notifications': '200',
      'POST /me/notifications/{notification_id}/read': '204',
      'POST /me/notifications/read-all': '204',
      'GET /verifier/applicants': '200',
      'GET /verifier/members': '200',
      'GET /verifier/people/{person_id}': '200',
      'POST /verifier/people/{person_id}/admit': '200',
      'POST /verifier/people/{person_id}/decline': '204',
      'GET /verifier/revoked': '200',
      'GET /verifier/flagged': '200',
      'PUT /verifier/people/{person_id}/status': '200',
      'POST /verifier/people/{person_id}/reconfirm': '200',
      'GET /group-requests': '200',
      'POST /group-requests': '201',
      'POST /group-requests/{request_id}/approve': '200',
      'POST /group-requests/{request_id}/decline': '204',
      'GET /move-requests': '200',
      'POST /move-requests': '201',
      'POST /move-requests/{request_id}/agree': '200',
      'POST /move-requests/{request_id}/cancel': '200',
      'PUT /home-groups/{group_id}/leader': '200',
      'POST /verifier/people/{person_id}/move': '200',
      'GET /verifier/group-invitations': '200',
      'POST /verifier/group-invitations': '201',
      'DELETE /verifier/group-invitations/{invitation_id}': '204',
      'POST /home-groups/{group_id}/close': '200',
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

  group('the church trust model', () {
    test('a person answer has the fields `PersonMe` reads', () {
      expect(
        properties('PersonMeResponse'),
        containsAll([
          'user_type',
          'id',
          'full_name',
          'email',
          'mobile_number',
          'status',
          'requested_status',
          'church',
          'home_group',
          'leader',
          'status_set_by',
          'flagged_for_recheck',
          'vouch_count',
        ]),
      );
      expect(
        responseSchema('PUT', '/me/application', '200'),
        'PersonMeResponse',
      );
    });

    test('the sign-up body carries what the wizard sends', () {
      expect(requestSchema('POST', '/auth/signup'), 'SignupRequest');
      expect(
        properties('SignupRequest'),
        containsAll([
          'full_name',
          'email',
          'mobile_number',
          'password',
          'requested_status',
          'home_group_id',
          'invitation_token',
        ]),
      );
      expect(required('SignupRequest'), {
        'full_name',
        'email',
        'mobile_number',
        'password',
        'requested_status',
      });
    });

    test('the lists the wizard reads', () {
      expect(responseSchema('GET', '/churches', '200'), 'ChurchList');
      expect(properties('ChurchSummary'), {'id', 'name'});
      expect(properties('HomeGroupSummary'), {'id', 'name', 'leader_name'});
      expect(properties('GroupInvitationInfo'), {
        'church_name',
        'home_group_name',
        'leader_name',
      });
    });

    test('a link token travels in the body, not in an address', () {
      expect(
        requestSchema('POST', '/group-invitations/lookup'),
        'GroupInvitationLookup',
      );
      expect(properties('GroupInvitationLookup'), {'token'});
    });

    test('closing the account sends the password', () {
      expect(requestSchema('DELETE', '/me'), 'CloseAccountRequest');
      expect(properties('CloseAccountRequest'), {'password'});
    });
  });

  group('vouching and notifications', () {
    test('a link is made once, and its token is not in the state answer', () {
      expect(
        responseSchema('POST', '/me/vouch-link', '201'),
        'VouchLinkCreated',
      );
      expect(properties('VouchLinkCreated'), {'token', 'expires_at'});
      expect(responseSchema('GET', '/me/vouch-link', '200'), 'VouchLinkState');
      expect(properties('VouchLinkState'), {'active', 'expires_at'});
    });

    test('the token travels in the body of the lookup and of the vouch', () {
      for (final path in ['/vouch-links/lookup', '/vouch-links/vouch']) {
        expect(requestSchema('POST', path), 'VouchLinkToken', reason: path);
      }
      expect(properties('VouchLinkToken'), {'token'});
    });

    test('the page a link opens has the fields `VouchLinkInfo` reads', () {
      expect(properties('VouchLinkInfo'), {
        'applicant_name',
        'church_name',
        'home_group_name',
        'requested_status',
        'already_vouched',
      });
    });

    test('the vouches received and given have the fields the app reads', () {
      expect(
        properties('VouchReceived'),
        containsAll([
          'id',
          'voucher_name',
          'church_name',
          'live',
          'created_at',
        ]),
      );
      expect(
        properties('VouchGiven'),
        containsAll([
          'id',
          'applicant_name',
          'applicant_status',
          'withdrawn',
          'can_withdraw',
          'created_at',
        ]),
      );
      expect(properties('VouchCreated'), {'id'});
    });

    test('a notification has the fields the list reads', () {
      expect(
        responseSchema('GET', '/me/notifications', '200'),
        'NotificationList',
      );
      expect(properties('NotificationList'), {
        'items',
        'total',
        'unread_count',
      });
      expect(
        properties('NotificationItem'),
        containsAll(['id', 'kind', 'subject', 'created_at', 'read']),
      );
    });

    test('applying to provide answers with the person', () {
      expect(
        responseSchema('POST', '/me/apply-provider', '200'),
        'PersonMeResponse',
      );
    });
  });

  group('the screens of a leader', () {
    test('the applicants list has the fields `ApplicantRow` reads', () {
      expect(
        responseSchema('GET', '/verifier/applicants', '200'),
        'ApplicantList',
      );
      expect(properties('ApplicantList'), {'items', 'total'});
      expect(
        properties('ApplicantRow'),
        containsAll([
          'id',
          'full_name',
          'status',
          'requested_status',
          'home_group',
          'applied_at',
          'vouch_count',
          'vouchers',
          'can_admit_as_provider',
        ]),
      );
      expect(properties('Voucher'), {'name', 'church_name', 'live'});
    });

    test('the members list has the fields `MemberRow` reads', () {
      expect(responseSchema('GET', '/verifier/members', '200'), 'MemberList');
      expect(
        properties('MemberRow'),
        containsAll([
          'id',
          'full_name',
          'status',
          'home_group',
          'status_set_by',
          'flagged_for_recheck',
        ]),
      );
    });

    test('one person has the fields `PersonDetail` reads, with the flag', () {
      expect(
        responseSchema('GET', '/verifier/people/{person_id}', '200'),
        'PersonDetail',
      );
      expect(
        properties('PersonDetail'),
        containsAll([
          'id',
          'full_name',
          'mobile_number',
          'status',
          'requested_status',
          'church',
          'home_group',
          'status_set_by',
          'applied_at',
          'history',
          'chain_of_trust',
          'vouches',
          'can_admit_as_provider',
          'flagged_for_recheck',
        ]),
      );
      expect(
        properties('HistoryEntry'),
        containsAll(['kind', 'from_status', 'to_status', 'changed_by', 'at']),
      );
      expect(properties('ChainLink'), {'id', 'full_name', 'status'});
    });

    test('admitting sends the status and reads the new one', () {
      expect(
        requestSchema('POST', '/verifier/people/{person_id}/admit'),
        'AdmitRequest',
      );
      expect(properties('AdmitRequest'), {'to'});
      expect(
        responseSchema('POST', '/verifier/people/{person_id}/admit', '200'),
        'AdmitResult',
      );
      expect(
        properties('AdmitResult'),
        containsAll(['status', 'requested_status']),
      );
    });

    test('the revoked and the flagged lists have the fields the app reads', () {
      expect(responseSchema('GET', '/verifier/revoked', '200'), 'RevokedList');
      expect(properties('RevokedList'), {'items', 'total'});
      expect(
        properties('RevokedRow'),
        containsAll([
          'id',
          'full_name',
          'removed_from',
          'revoked_by',
          'revoked_at',
        ]),
      );
      expect(responseSchema('GET', '/verifier/flagged', '200'), 'FlaggedList');
      expect(properties('FlaggedList'), {'items', 'total'});
      expect(
        properties('FlaggedRow'),
        containsAll([
          'id',
          'full_name',
          'status',
          'home_group',
          'status_set_by',
        ]),
      );
    });

    test(
      'revoking and reinstating send a status, and answer with the new one',
      () {
        expect(
          requestSchema('PUT', '/verifier/people/{person_id}/status'),
          'StatusRequest',
        );
        // The app sends `to` and, to reinstate, `home_group_id`; the successors are for leaders.
        expect(
          properties('StatusRequest'),
          containsAll([
            'to',
            'home_group_id',
            'successor_id',
            'group_successor_id',
          ]),
        );
        expect(
          responseSchema('PUT', '/verifier/people/{person_id}/status', '200'),
          'StatusResult',
        );
        expect(
          responseSchema(
            'POST',
            '/verifier/people/{person_id}/reconfirm',
            '200',
          ),
          'StatusResult',
        );
        expect(
          properties('StatusResult'),
          containsAll(['id', 'status', 'home_group_id', 'flagged_for_recheck']),
        );
      },
    );

    test('the group requests have the fields the app reads and sends', () {
      expect(
        responseSchema('GET', '/group-requests', '200'),
        'GroupRequestList',
      );
      expect(properties('GroupRequestList'), {'items', 'total'});
      expect(
        properties('GroupRequestOut'),
        containsAll([
          'id',
          'group_name',
          'church',
          'requester',
          'state',
          'created_at',
          'requester_leads_a_group',
          'requester_group',
        ]),
      );
      expect(
        responseSchema('POST', '/group-requests', '201'),
        'GroupRequestCreated',
      );
      expect(properties('GroupRequestCreated'), {'request', 'group'});
      expect(properties('GroupRequestCreate'), {'group_name', 'successor_id'});
      expect(properties('GroupRequestApprove'), {'successor_id'});
      expect(
        responseSchema('POST', '/group-requests/{request_id}/approve', '200'),
        'GroupStarted',
      );
      expect(properties('GroupStarted'), {'group'});
      // The nested names the app reads (who asks, which church, which group) are all `IdName`,
      // which has exactly the `id` and `name` it reads.
      expect(properties('IdName'), {'id', 'name'});
      for (final field in ['church', 'requester', 'requester_group']) {
        expect(refsOf('GroupRequestOut', field), {'IdName'}, reason: field);
      }
      expect(refsOf('GroupRequestCreated', 'group'), {'IdName'});
      expect(refsOf('GroupRequestCreated', 'request'), {'GroupRequestOut'});
      expect(refsOf('GroupStarted', 'group'), {'IdName'});
    });

    test('the move requests have the fields the app reads and sends', () {
      expect(responseSchema('GET', '/move-requests', '200'), 'MoveRequestList');
      expect(properties('MoveRequestList'), {'items', 'total'});
      expect(
        properties('MoveRequestOut'),
        containsAll([
          'id',
          'person',
          'from_group',
          'to_group',
          'agreed',
          'state',
          'created_at',
        ]),
      );
      for (final field in ['person', 'from_group', 'to_group']) {
        expect(refsOf('MoveRequestOut', field), {'IdName'}, reason: field);
      }
      expect(refsOf('MoveRequestOut', 'agreed'), {'MoveAgreements'});
      expect(properties('MoveAgreements'), {
        'person',
        'from_leader',
        'to_leader',
      });
      expect(properties('MoveRequestCreate'), {'home_group_id'});
      expect(responseSchema('POST', '/move-requests', '201'), 'MoveRequestOut');
      expect(
        responseSchema('POST', '/move-requests/{request_id}/agree', '200'),
        'MoveRequestOut',
      );
      expect(
        responseSchema('POST', '/move-requests/{request_id}/cancel', '200'),
        'MoveRequestOut',
      );
    });

    test(
      'changing a leader and moving a member have the fields the app uses',
      () {
        expect(properties('LeaderChange'), {
          'successor_id',
          'former_leader_status',
        });
        expect(
          responseSchema('PUT', '/home-groups/{group_id}/leader', '200'),
          'LeaderChanged',
        );
        expect(properties('LeaderChanged'), {'group', 'leader'});
        expect(refsOf('LeaderChanged', 'group'), {'IdName'});
        expect(refsOf('LeaderChanged', 'leader'), {'IdName'});
        expect(properties('DirectMove'), {'home_group_id'});
        expect(
          responseSchema('POST', '/verifier/people/{person_id}/move', '200'),
          'Moved',
        );
        expect(properties('Moved'), {'person', 'home_group'});
        expect(refsOf('Moved', 'home_group'), {'IdName'});
      },
    );

    test('the group invitation links have the fields the app reads', () {
      expect(
        responseSchema('GET', '/verifier/group-invitations', '200'),
        'GroupInvitationList',
      );
      expect(properties('GroupInvitationList'), {'items'});
      expect(properties('GroupInvitationSummary'), {
        'id',
        'created_at',
        'expires_at',
      });
      expect(
        responseSchema('POST', '/verifier/group-invitations', '201'),
        'GroupInvitationCreated',
      );
      expect(properties('GroupInvitationCreated'), {
        'id',
        'token',
        'expires_at',
      });
      // The list never carries a token: it was shown once, when the link was made.
      expect(properties('GroupInvitationSummary'), isNot(contains('token')));
    });

    test('closing one\'s own group has the fields the app uses', () {
      expect(properties('GroupClose'), {
        'move_to_group_id',
        'former_leader_status',
      });
      expect(
        responseSchema('POST', '/home-groups/{group_id}/close', '200'),
        'GroupClosed',
      );
      expect(properties('GroupClosed'), {
        'closed_group',
        'joined_group',
        'status',
      });
      expect(refsOf('GroupClosed', 'closed_group'), {'IdName'});
      expect(refsOf('GroupClosed', 'joined_group'), {'IdName'});
    });

    test('only the person page has a number', () {
      for (final schema in [
        'ApplicantRow',
        'MemberRow',
        'FlaggedRow',
        'Voucher',
        'VouchReceived',
        'VouchGiven',
        'VouchLinkInfo',
        'ChainLink',
        'HistoryEntry',
        'NotificationItem',
      ]) {
        expect(properties(schema), isNot(contains('mobile_number')));
      }
      expect(properties('PersonDetail'), contains('mobile_number'));
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
