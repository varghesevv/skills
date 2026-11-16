/// Messages, for a SEARCHER or above: the list, and one conversation at `/member/chat/<id>`.
const chatList = '/member/chat';
const chatThreadBase = '/member/chat';

String chatThread(String id) => '$chatThreadBase/$id';
