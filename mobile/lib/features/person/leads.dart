import '../../core/auth/person_me.dart';

/// Does this person lead the group they belong to? `/me` carries only the leader's name, so the
/// names are compared; the server decides in the end, and a wrong guess only shows a choice the
/// server then refuses in words.
bool leadsOwnGroup(PersonMe person) =>
    person.homeGroup != null &&
    person.status.isLeader &&
    person.leaderName == person.fullName;
