import 'package:flutter_test/flutter_test.dart';
import 'package:skills_app/core/terminology/app_config.dart';
import 'package:skills_app/core/terminology/terms.dart';

// The words below are what the server returns for each profile in `GET /app/config`. They are test
// data only: the app itself carries no word profile.
const _defaultWords = {
  'organisation': 'Organisation',
  'organisations': 'Organisations',
  'workhost': 'Work host',
  'workhosts': 'Work hosts',
  'freelancer': 'Freelancer',
  'freelancers': 'Freelancers',
}; // fmt: skip
const _churchWords = {
  'organisation': 'Church',
  'organisations': 'Churches',
  'workhost': 'Searcher',
  'workhosts': 'Searchers',
  'freelancer': 'Provider',
  'freelancers': 'Providers',
}; // fmt: skip

const _structureDefault = {
  'homegroup': 'Home group',
  'homegroups': 'Home groups',
  'verifier': 'Verifier',
  'admin': 'Admin',
  'owner': 'Owner',
}; // fmt: skip
const _structureChurch = {
  'homegroup': 'Home group',
  'homegroups': 'Home groups',
  'verifier': 'Group leader',
  'admin': 'Church admin',
  'owner': 'Owner',
}; // fmt: skip

void main() {
  const base = Terms(_defaultWords);
  const church = Terms(_churchWords);

  group('apply', () {
    test('keeps the default words', () {
      expect(
        base.apply('Vouch for {freelancers}. {Organisations} and {workhosts}.'),
        'Vouch for freelancers. Organisations and work hosts.',
      );
      expect(
        base.apply('I represent {a_organisation}'),
        'I represent an organisation',
      );
      expect(base.apply('{Workhost}'), 'Work host');
    });

    test('switches to the church words and fixes the article', () {
      expect(
        church.apply('{Organisations} and {workhosts}'),
        'Churches and searchers',
      );
      expect(
        church.apply('I represent {a_organisation}'),
        'I represent a church',
      );
      expect(church.apply('{A_workhost} helps'), 'A searcher helps');
      expect(
        church.apply('Find {freelancers}, {a_freelancer}'),
        'Find providers, a provider',
      );
      expect(church.apply('{Organisation} Name'), 'Church Name');
    });

    test('knows the words of the church trust model', () {
      const plain = Terms({..._defaultWords, ..._structureDefault});
      const churchy = Terms({..._churchWords, ..._structureChurch});
      expect(
        plain.apply('{Homegroup}, {homegroups}, {verifier}, {Admin}'),
        'Home group, home groups, verifier, Admin',
      );
      expect(
        churchy.apply('{Verifier} and {admin} and {Owner}'),
        'Group leader and church admin and Owner',
      );
      expect(
        churchy.apply('{a_verifier}, {a_admin}'),
        'a group leader, a church admin',
      );
    });

    test(
      'a word the server does not send is shown readably, not as a token',
      () {
        const older = Terms(_defaultWords); // no structure words
        expect(older.apply('Status: {Verifier}'), 'Status: Verifier');
        expect(older.apply('{a_admin} and {owners}'), 'an admin and owners');
        expect(older.apply('{A_verifier}'), 'A verifier');
      },
    );

    test('leaves other placeholders alone', () {
      expect(
        base.apply('{count} {freelancer}(s) on page {page}'),
        '{count} freelancer(s) on page {page}',
      );
    });
  });

  test('term throws for an unknown key', () {
    expect(() => base.term('nope'), throwsStateError);
  });

  group('AppConfig', () {
    final config = AppConfig.fromJson({
      'terminology': {'profile': 'church', 'terms': _churchWords},
      'app': {'min_version': '1.2.0', 'latest_version': '1.10.0'},
    });

    test('reads the server answer', () {
      expect(config.profile, 'church');
      expect(config.terms.term('workhost'), 'Searcher');
    });

    test('compares versions as numbers and ignores the build number', () {
      expect(config.requiresUpdate('1.1.9'), isTrue);
      expect(config.requiresUpdate('1.2.0+7'), isFalse);
      expect(
        config.updateAvailable('1.9.0'),
        isTrue,
      ); // text order would say 1.9.0 > 1.10.0
      expect(config.updateAvailable('1.10.0'), isFalse);
    });

    test('a version that cannot be read never blocks', () {
      expect(
        AppConfig.fromJson({
          'terminology': {'profile': 'default', 'terms': _defaultWords},
          'app': {'min_version': '0.0.0', 'latest_version': '0.0.0'},
        }).requiresUpdate('dev'),
        isFalse,
      );
    });
  });
}
