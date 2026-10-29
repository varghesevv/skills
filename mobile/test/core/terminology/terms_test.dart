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
  'workhost': 'Provider',
  'workhosts': 'Providers',
  'freelancer': 'Searcher',
  'freelancers': 'Searchers',
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
        'Churches and providers',
      );
      expect(
        church.apply('I represent {a_organisation}'),
        'I represent a church',
      );
      expect(church.apply('{A_workhost} helps'), 'A provider helps');
      expect(
        church.apply('Find {freelancers}, {a_freelancer}'),
        'Find searchers, a searcher',
      );
      expect(church.apply('{Organisation} Name'), 'Church Name');
    });

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
      expect(config.terms.term('workhost'), 'Provider');
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
