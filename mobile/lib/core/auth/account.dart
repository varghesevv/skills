/// Who is signed in: an older account (`Me`) or a person of the church trust model (`PersonMe`).
/// While both exist (roadmap decision D-20) the session holds one of them; the older accounts go
/// with their features (S5).
abstract class Account {
  const Account();
}
