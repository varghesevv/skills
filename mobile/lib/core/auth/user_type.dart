/// The stored `user_type` values. They never change with the wording shown to people.
/// The app has no admin login, so there is no `admin` value to send.
enum UserType {
  freelancer('freelancer'),
  workhost('workhost'),
  organisation('organisation');

  const UserType(this.wire);

  /// The value sent to and received from the API.
  final String wire;

  static UserType fromWire(String value) => UserType.values.firstWhere(
    (type) => type.wire == value,
    orElse: () => throw FormatException('Unknown user type'),
  );
}
