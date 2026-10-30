/// Client-side form rules. They mirror `backend/app/schemas/auth.py` and
/// `frontend/src/shared/validation.ts`; the server stays the authority and this only saves a
/// round trip. A validator returns a string key (see `strings_en.dart`) or null when the value is
/// fine. Field names match the API so server field errors line up.
library;

const minPasswordLength = 10;
const maxPasswordLength = 128;

String? requiredEmail(String value) {
  final text = value.trim();
  if (text.isEmpty) return 'validation.required';
  if (text.length > 254 || !_email.hasMatch(text)) return 'validation.email';
  return null;
}

// Deliberately simple, like a form check: something@something.tld without spaces.
final _email = RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$');

String? requiredPassword(String value) {
  if (value.isEmpty) return 'validation.required';
  if (value.length > 1024) return 'validation.tooLong';
  return null;
}

String? newPassword(String value) {
  if (value.length < minPasswordLength) return 'validation.passwordShort';
  if (value.length > maxPasswordLength) return 'validation.passwordLong';
  return null;
}

String? fullName(String value) {
  final length = value.trim().length;
  return length < 2 || length > 200 ? 'validation.fullName' : null;
}

String? orgName(String value) {
  final length = value.trim().length;
  return length < 2 || length > 200 ? 'validation.orgName' : null;
}

/// Spaces and dashes are removed before the check; use [normaliseMobile] for the value to send.
String? mobile(String value) =>
    _mobile.hasMatch(normaliseMobile(value)) ? null : 'validation.mobile';

final _mobile = RegExp(r'^\+?[0-9]{7,15}$');

String normaliseMobile(String value) => value.replaceAll(RegExp(r'[ -]'), '');

String? optionalText(String value) =>
    value.trim().length > 100 ? 'validation.tooLong' : null;

/// Field name -> message key, for the fields that failed. Empty when the form is valid.
typedef FieldKeys = Map<String, String>;

FieldKeys _collect(Map<String, String? Function()> checks) {
  final failed = <String, String>{};
  checks.forEach((field, check) {
    final key = check();
    if (key != null) failed[field] = key;
  });
  return failed;
}

FieldKeys validateLogin({required String email, required String password}) =>
    _collect({
      'email': () => requiredEmail(email),
      'password': () => requiredPassword(password),
    });

FieldKeys validateForgotPassword({required String email}) =>
    _collect({'email': () => requiredEmail(email)});

FieldKeys validateRegistration({
  required String type, // 'freelancer' | 'workhost' | 'organisation'
  required String name, // full name, or organisation name for an organisation
  required String email,
  required String mobileNumber,
  required String password,
  String nationality = '',
  String primaryLanguage = '',
}) {
  final isOrganisation = type == 'organisation';
  return _collect({
    if (isOrganisation)
      'org_name': () => orgName(name)
    else
      'full_name': () => fullName(name),
    'email': () => requiredEmail(email),
    'mobile_number': () => mobile(mobileNumber),
    'password': () => newPassword(password),
    if (type == 'freelancer') ...{
      'nationality': () => optionalText(nationality),
      'primary_language': () => optionalText(primaryLanguage),
    },
  });
}

/// Up to 8 digits and 2 decimals (the API stores numeric(10,2)). Empty means "no rate".
String? rate(String value) =>
    RegExp(r'^(\d{1,8}(\.\d{1,2})?)?$').hasMatch(value.trim())
    ? null
    : 'validation.rate';

/// Three letters (ISO 4217), typed in any case; use [normaliseCurrency] for the value to send.
String? currency(String value) =>
    RegExp(r'^([A-Z]{3})?$').hasMatch(normaliseCurrency(value))
    ? null
    : 'validation.currency';

String normaliseCurrency(String value) => value.trim().toUpperCase();

FieldKeys validateFreelancerProfile({
  required String fullNameValue,
  required String mobileNumber,
  required String nationality,
  required String primaryLanguage,
  required String ratePerHour,
  required String rateCurrency,
}) {
  final failed = _collect({
    'full_name': () => fullName(fullNameValue),
    'mobile_number': () => mobile(mobileNumber),
    'nationality': () => optionalText(nationality),
    'primary_language': () => optionalText(primaryLanguage),
    'rate_per_hour': () => rate(ratePerHour),
    'rate_currency': () => currency(rateCurrency),
  });
  // A rate and its currency go together: both or neither.
  final noRate = ratePerHour.trim().isEmpty;
  final noCurrency = normaliseCurrency(rateCurrency).isEmpty;
  if (noRate != noCurrency) {
    failed.putIfAbsent(
      noRate ? 'rate_per_hour' : 'rate_currency',
      () => 'validation.rateTogether',
    );
  }
  return failed;
}
