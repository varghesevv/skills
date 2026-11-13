import '../../core/api/api_exception.dart';
import '../../core/strings/app_text.dart';

/// What a refused admit or decline means for a leader. The server's code decides the words.
String leaderProblem(AppText text, Object error) {
  if (error is ApiException) {
    switch (error.code) {
      case 'not_enough_vouches':
        return text('leader.error.notEnough');
      case 'not_pending':
        return text('leader.error.notPending');
      case 'state_changed':
        return text('leader.error.changed');
    }
  }
  return text.error(error);
}
