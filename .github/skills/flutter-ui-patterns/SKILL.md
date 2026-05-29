---
name: "flutter-ui-patterns"
description: "Patterns for building Flutter UI — Riverpod state management, Freezed domain models, GoRouter navigation, Material 3 components, repository abstraction, and widget composition. Use this skill whenever creating or modifying Flutter features, screens, pages, widgets, buttons, FABs, forms, or shared UI components — even for small changes like adding a button or action to an existing page. Also use when choosing between button types (FAB, FilledButton, OutlinedButton, TextButton) or deciding how to lay out actions on a screen."
metadata:
  tags: default
---

# Flutter UI Patterns

## Module Structure

Feature-based modular architecture:

```
lib/
├── features/
│   └── [feature_name]/
│       ├── domain/             # Freezed domain models
│       ├── providers/          # Riverpod providers
│       ├── repositories/       # Data access layer
│       └── views/              # Pages and widgets
├── shared/
│   ├── domain/                 # Shared domain models
│   ├── providers/              # Global providers
│   ├── repositories/           # Shared repositories
│   ├── util/                   # API client, helpers, mixins
│   └── widgets/                # Reusable widgets
├── main.dart
└── router.dart
```

## Component Catalog

Before creating a new shared widget or utility, read `references/component-catalog.md` for the full list of existing reusable components with usage examples. Prefer reusing a cataloged component over building a new one. If you add a new shared component, add it to the catalog.

---

## State Management (Riverpod)

Use **Riverpod v3 with code generation** (`riverpod_annotation`). Always add `part 'filename.g.dart'`.

```dart
// Simple computed state
@riverpod
bool hasAdminAccess(Ref ref) {
  final adminAccess = ref.watch(adminAccessProvider);
  return adminAccess.hasAdminAccess;
}

// Async data with lifecycle (AsyncNotifier)
@riverpod
class UserNotifier extends _$UserNotifier {
  final _repository = UserRepository();

  @override
  Future<User> build() async => await _repository.getUser();

  Future<void> updateUser(User user) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _repository.updateUser(user));
  }
}

// Parameterized (Family)
@riverpod
Future<Property> propertyDetails(Ref ref, String propertyId) async {
  return await PropertyRepository().getProperty(propertyId);
}

// Keep-alive singleton
@Riverpod(keepAlive: true)
class GlobalCacheNotifier extends _$GlobalCacheNotifier {
  @override
  Map<String, dynamic> build() => {};
}
```

### Provider Guidelines

- `ref.watch()` — reactive dependencies (use in `build`)
- `ref.read()` — one-time reads (use in event handlers)
- `ref.invalidateSelf()` — refresh provider data
- `ref.onDispose(() { ... })` — register cleanup callbacks for subscriptions and controllers

### Optimistic Updates

```dart
Future<void> deleteItem(String id) async {
  final previousList = state.value ?? [];
  state = AsyncValue.data(previousList.where((item) => item.id != id).toList());
  try {
    await _repository.deleteItem(id);
  } catch (e) {
    state = AsyncValue.data(previousList);
    rethrow;
  }
}
```

---

## Domain Objects (Freezed)

```dart
@freezed
abstract class User with _$User {
  const factory User({
    required String id,
    required String email,
    @JsonKey(name: 'display_name') String? displayName,
    @JsonKey(name: 'user_type') required UserTypeEnum userType,
    @JsonKey(name: 'created_at') required DateTime createdAt,
    required bool active,
  }) = _User;

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
}

// Union types (sealed classes)
@Freezed(unionKey: "type")
abstract class MessageAuthor with _$MessageAuthor {
  @FreezedUnionValue("AI_AGENT")
  const factory MessageAuthor.aiAgent() = _AiAgent;

  @FreezedUnionValue("USER")
  const factory MessageAuthor.user({required String userId}) = _User;
}

// Enums with JSON values
enum UserTypeEnum {
  @JsonValue('HOMEOWNER') homeowner,
  @JsonValue('ADMIN') admin,
}
```

- Always use `@JsonKey(name: 'api_field')` for snake_case API field mapping
- Use `DateTime` for all timestamps
- Use union types for polymorphic API responses

---

## Repository Pattern

```dart
mixin ApiRepositoryMixin {
  ApiClient get apiClient => ApiClient();

  Future<T> safeApiCall<T>(
    Future<http.Response> Function() request,
    T Function(dynamic json) parser, {
    String? errorMessage,
  }) async {
    final response = await request();
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return parser(jsonDecode(response.body));
    }
    throw HttpException(errorMessage ?? 'API request failed');
  }
}

class UserRepository with ApiRepositoryMixin {
  Future<User> getUser() async {
    return safeApiCall(
      () => apiClient.get("/api/users/me"),
      (json) => User.fromJson(json),
    );
  }

  Future<List<User>> getUsers({String? searchQuery}) async {
    final params = <String, String>{};
    if (searchQuery != null) params['q'] = searchQuery;
    return safeApiCall(
      () => apiClient.get('/api/users', queryParameters: params),
      (json) => (json as List).map((item) => User.fromJson(item)).toList(),
    );
  }
}
```

- One repository per domain aggregate
- Create new instances per use — repositories are stateless
- Build query params as `Map<String, String>`

---

## Routing (GoRouter)

```dart
final GoRouter router = GoRouter(
  initialLocation: '/home',
  routes: [
    GoRoute(path: '/login', builder: (context, state) => const LoginPage()),
    GoRoute(
      path: '/profile',
      builder: (context, state) => const ProfilePage(),
      redirect: authenticatedRedirect,
    ),
    StatefulShellRoute.indexedStack(
      pageBuilder: (context, state, navigationShell) =>
          NoTransitionPage(child: MainScaffold(shell: navigationShell)),
      branches: [
        StatefulShellBranch(routes: [
          GoRoute(path: '/home', builder: (_, __) => const HomePage()),
        ]),
      ],
    ),
  ],
  redirect: globalRedirect,
);

String? authenticatedRedirect(BuildContext context, GoRouterState state) {
  final loggedIn = FirebaseAuth.instance.currentUser != null;
  return loggedIn ? null : '/login';
}
```

- Use `NoTransitionPage` for web-style navigation
- Use `StatefulShellRoute` for persistent bottom/side navigation
- Use path parameters for entity IDs: `/items/:itemId`

---

## API Client

```dart
class ApiClient {
  static const String _baseUrl = String.fromEnvironment("HTTP_SERVICE_URL");
  final FirebaseAuth _auth = FirebaseAuth.instance;

  Future<Map<String, String>> _getHeaders() async {
    final token = await _auth.currentUser?.getIdToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<http.Response> get(String endpoint, {Map<String, String>? queryParameters}) async {
    final headers = await _getHeaders();
    var uri = Uri.parse('$_baseUrl$endpoint');
    if (queryParameters != null) uri = uri.replace(queryParameters: queryParameters);
    return http.get(uri, headers: headers);
  }

  Future<http.Response> post(String endpoint, Map<String, dynamic> body) async {
    return http.post(
      Uri.parse('$_baseUrl$endpoint'),
      headers: await _getHeaders(),
      body: jsonEncode(body),
    );
  }

  Future<http.Response> put(String endpoint, Map<String, dynamic> body) async {
    return http.put(
      Uri.parse('$_baseUrl$endpoint'),
      headers: await _getHeaders(),
      body: jsonEncode(body),
    );
  }

  Future<http.Response> delete(String endpoint) async {
    return http.delete(
      Uri.parse('$_baseUrl$endpoint'),
      headers: await _getHeaders(),
    );
  }
}
```

---

## Widget Patterns

```dart
// ConsumerWidget (stateless + providers)
class UserProfilePage extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(userProvider);
    return userAsync.when(
      data: (user) => _buildProfile(user),
      loading: () => const CircularProgressIndicator(),
      error: (err, stack) => ErrorWidget(message: err.toString()),
    );
  }
}

// ConsumerStatefulWidget (lifecycle + providers)
class ChatPage extends ConsumerStatefulWidget {
  final String conversationId;
  const ChatPage({super.key, required this.conversationId});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Initialize after first frame
    });
  }
}
```

---

## Material Design 3

Read `references/m3-foundations.md` for any M3 work — it covers the theme, color tokens, button hierarchy, and global rules, and contains a routing table to the per-component references.

Component-specific guidance lives in `references/m3/`:

| Building / modifying… | Read |
|-----------------------|------|
| Menus, dropdowns, overflow, context menus | `references/m3/menus.md` |
| FABs (single or expandable) | `references/m3/fabs.md` |
| `NavigationBar` / `NavigationRail` | `references/m3/navigation.md` |
| App bar actions, icon buttons, overflow placement | `references/m3/app-bar.md` |
| Delete / archive / any destructive flow | `references/m3/destructive-actions.md` |

Rules to always follow (full reasoning in the references above):

1. **FABs are for creation only** (add, compose) — never for contextual actions (save, next, submit). Use `FilledButton` for those.
2. **One FilledButton per view/dialog** — multiple filled buttons dilute emphasis. Use `OutlinedButton` for secondary actions.
3. **Menus are for choosing, not for primary actions** — prefer `MenuAnchor` for new code; `DropdownMenu` for form selection.
4. **Color the commit, not the trigger** — `colorScheme.error` belongs on menu labels and dialog confirm buttons, not on standalone icon buttons.
5. Always use M3 components — `NavigationBar` not `BottomNavigationBar`, `FilledButton` not `ElevatedButton`.
6. Use `ColorScheme` tokens — never hardcode hex values.
7. Spacing in 4dp increments: 4, 8, 12, 16, 24, 32, 48.

---

## Mixins

```dart
mixin SubscriptionMixin {
  StreamSubscription? _subscription;

  void subscribe(Stream stream, void Function(dynamic) onData) {
    _subscription = stream.listen(onData);
  }

  void unsubscribe() => _subscription?.cancel();
}
```

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_riverpod` + `riverpod_annotation` | State management |
| `freezed_annotation` + `freezed` | Immutable models |
| `json_annotation` + `json_serializable` | JSON serialization |
| `go_router` | Navigation |
| `firebase_auth` | Authentication |
| `http` | HTTP client |
| `event_flux` | Server-Sent Events |
