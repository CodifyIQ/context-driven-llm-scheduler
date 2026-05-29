---
name: "Dart/Flutter Standards"
description: "Coding conventions for all Dart files — naming, null safety, const usage, widget structure, and performance"
applyTo: "**/*.dart"
---

# Dart/Flutter Coding Conventions

## Minimalist Implementation

- Always implement the absolute minimum needed to meet the specified task requirements
- When in doubt about scope, choose the narrower interpretation
- Prefer simple, direct solutions over clever ones

## Naming

- Files and folders: `snake_case` (e.g., `user_profile_page.dart`, `features/auth/`)
- Variables and functions: `camelCase` (e.g., `isLoading`, `hasError`, `fetchUser`)
- Classes, enums, typedefs: `PascalCase` (e.g., `UserRepository`, `AuthState`)
- Private members: `_leadingUnderscore`
- Use descriptive names with auxiliary verbs for booleans: `isLoading`, `hasError`, `canDelete`

## Imports

- Always use package imports (e.g., `import 'package:myapp/features/auth/views/login_page.dart'`)
- Never use relative imports (e.g., avoid `import '../views/login_page.dart'`)
- This ensures consistent resolution regardless of file location

## Null Safety

- Enable null safety — it is required in all code
- Use `?` sparingly — only when null is a meaningful, expected value
- Prefer `??` over explicit null checks for default values
- Use `!` (bang operator) only when null is provably impossible; add a comment explaining why

```dart
// Prefer
final name = user.displayName ?? 'Anonymous';

// Avoid
final name = user.displayName != null ? user.displayName! : 'Anonymous';
```

## Const Usage

- Use `const` constructors everywhere possible — it is a performance optimization
- Mark widget constructors `const` whenever all fields are compile-time constants
- Use `const` for static values, colors, padding, and text styles

```dart
// Correct
const SizedBox(height: 16)
const EdgeInsets.symmetric(horizontal: 24)
const Text('Hello')

// Use const on the variable too when applicable
const padding = EdgeInsets.all(16);
```

## Widget Structure

- Keep widgets under 100 lines — extract to separate files if larger
- Prefer `StatelessWidget` over `StatefulWidget` when state is managed externally (e.g., via Riverpod)
- Give extracted widgets descriptive names that communicate purpose and context
- Always declare a `const` constructor on stateless widgets

```dart
class UserAvatarWidget extends StatelessWidget {
  const UserAvatarWidget({super.key, required this.user});

  final User user;

  @override
  Widget build(BuildContext context) { ... }
}
```

## Performance

- Avoid the `Opacity` widget for animations — use `AnimatedOpacity` or `FadeTransition`
- Avoid `saveLayer` and clipping in hot render paths
- Use `ListView.builder()` for dynamic lists — never build large static widget trees
- Minimize layout passes — avoid nested `Expanded`/`Flexible` chains that require intrinsic measurements
- Avoid rebuilding expensive subtrees on every frame — use `const` or extract widgets with stable references

## Error Handling

- Implement proper error handling in all async code
- Use Riverpod's `AsyncValue.error` state to surface errors in the UI
- Show meaningful error messages — never silently swallow exceptions

## Code Style

- Prefer composition over inheritance for widget reuse
- Use `@override` annotation on all overriding methods
- Trailing commas on multi-line argument lists — this keeps `dartfmt` formatting clean
- Use `super.key` shorthand in constructors (Dart 3+)

## Code Generation

After modifying `@freezed`, `@riverpod`, or `@JsonSerializable` annotated files:

```bash
dart run build_runner build --delete-conflicting-outputs
```

Always add the generated part file declaration:

```dart
part 'filename.g.dart';
```
