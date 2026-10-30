/// One label of the catalogue (`GET /labels`): a skill, language, timing, nativity or skill level.
class Label {
  const Label({
    required this.id,
    required this.name,
    required this.type,
    required this.isActive,
  });

  factory Label.fromJson(Map<String, Object?> json) => Label(
    id: json['id'] as String,
    name: json['label_name'] as String,
    type: json['label_type'] as String,
    isActive: (json['is_active'] as bool?) ?? true,
  );

  final String id;
  final String name;
  final String type; // skill | language | timing | nativity | skill_level
  final bool isActive;
}

/// A label the freelancer has chosen, with the level for a skill.
class ProfileLabel {
  const ProfileLabel({required this.label, required this.level});

  factory ProfileLabel.fromJson(Map<String, Object?> json) => ProfileLabel(
    label: Label.fromJson(Map<String, Object?>.from(json['label'] as Map)),
    level: json['level'] == null
        ? null
        : Label.fromJson(Map<String, Object?>.from(json['level'] as Map)),
  );

  final Label label;
  final Label? level;
}

/// One entry of `PUT /freelancers/me/labels`. A level only goes with a skill.
class LabelSelection {
  const LabelSelection({required this.labelId, this.levelId});

  final String labelId;
  final String? levelId;

  Map<String, Object?> toJson() => {
    'label_id': labelId,
    'level_label_id': levelId,
  };
}

/// Skill levels such as "basic", "50%", "80%": words first, then by number. Port of `sortLevels`
/// in the web app, so both show the same order.
List<Label> sortLevels(List<Label> levels) {
  int rank(Label label) {
    final match = RegExp(r'^\s*[-+]?\d+').firstMatch(label.name);
    return match == null ? -1 : int.parse(match.group(0)!.trim());
  }

  final sorted = [...levels];
  sorted.sort((a, b) {
    final byRank = rank(a).compareTo(rank(b));
    return byRank != 0
        ? byRank
        : a.name.toLowerCase().compareTo(b.name.toLowerCase());
  });
  return sorted;
}
