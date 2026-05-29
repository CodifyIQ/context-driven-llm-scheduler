# Component Catalog

Before building new UI, check this catalog. Prefer reusing an existing component over creating a new one. If you add a new shared widget or utility, add it here.

## Widgets (`shared/widgets/`)

**`SwipeDetailScaffold`** — Scaffold with PageView for swiping between a list of items. Provides AppBar with title and "N of M" counter.
```dart
SwipeDetailScaffold(
  itemIds: vendorIds,
  initialIndex: index,
  titleBuilder: (id) => _AppBarTitle(vendorId: id),
  contentBuilder: (id) => _DetailContent(vendorId: id),
  floatingActionButton: (currentIndex) => FloatingActionButton(...), // optional
  onIndexChanged: (index) => setState(() => _currentIndex = index), // optional
)
```

**`AsyncErrorWidget`** — Centered error message with retry button. Use as the `error` branch of `AsyncValue.when()`.
```dart
AsyncErrorWidget(
  message: 'Failed to load invoices',
  error: error,
  onRetry: () => ref.invalidate(invoiceListProvider),
)
```

**`ListHeader`** — Subtle explanatory text above a list (sort order, data summary).
```dart
ListHeader(message: 'Sorted by frequency, then spend.')
```

**`MetricColumn`** — Vertically stacked label+value pair for summary cards. Supports tappable styling.
```dart
MetricColumn(label: 'Total Spend', value: '\$1,234.56', isTappable: true)
```

**`SummarySectionCard`** — One section row on a landing-page hub. Title + count + optional hot-item chips + chevron; the whole card is the tap target (hot items are informational, not separately tappable). Used by the Ordering and Inventory landings to summarize their sub-areas.
```dart
SummarySectionCard(
  icon: Icons.inventory_2_outlined,
  title: 'Inventory',
  count: 47,
  hotItems: const ['Eggs (~3d)', 'Butter (~5d)'],
  onTap: () => context.go('/inventory/items'),
)
```

**`InvoiceCard`** — Tappable card displaying an `InvoiceSummary` that navigates to invoice detail. Set `showStatus: true` for the full layout with status chips.
```dart
InvoiceCard(
  invoice: invoice,
  invoiceIds: invoiceIds,
  index: index,
  showStatus: true, // false for simplified vendor invoices view
)
```

**`ContentStatusChip`** — Status chip for ingested-content lists. Takes a status string and a `Map<String, StatusChipStyle>` for per-status color/icon. Used by both invoice and recipe import cards.
```dart
ContentStatusChip(
  status: 'PENDING',
  styles: {
    'PROCESSED': StatusChipStyle(color: Colors.green, icon: Icons.check_circle_outline),
    'FAILED': StatusChipStyle(color: Colors.red, icon: Icons.error_outline),
    'PENDING': StatusChipStyle(color: Colors.orange, icon: Icons.hourglass_empty),
  },
)
```

**`IngestedContentCard`** — Tappable card shell for ingested content (invoices, recipe imports). Provides title row with optional status chip or trailing widget, optional subtitle, and optional bottom widget for domain-specific details.
```dart
IngestedContentCard(
  title: 'Vendor Name',
  subtitle: 'invoice_20260415.pdf',
  status: 'PENDING',
  statusStyles: invoiceStatusStyles,
  bottom: Text('3 items'),
  onTap: () => context.push('/invoices/$id'),
)
```

**`InventoryTrendChart`** — Plots cumulative inventory from transaction events with a burndown projection. Requires `fl_chart`.
```dart
InventoryTrendChart(
  transactions: item.transactions,
  currentQuantity: item.currentQuantity,
  unit: 'cases',
  height: 180, // default
)
```

**`RefinementChatSheet`** — Bottom sheet for conversational refinement of invoices or recipes. Built on flutter_chat_ui (Flyer Chat) with `FlyerChatTextMessage` builders and a `LocalChatController`. Opens a chat session with the backend LangGraph agent, displays messages with suggestion chips, and calls `onMutations` when the agent makes data changes so the parent can refresh.
```dart
showModalBottomSheet(
  context: context,
  isScrollControlled: true,
  useSafeArea: true,
  builder: (context) => DraggableScrollableSheet(
    initialChildSize: 0.6,
    minChildSize: 0.3,
    maxChildSize: 0.9,
    expand: false,
    builder: (context, scrollController) => RefinementChatSheet(
      domain: 'INVOICE', // or 'RECIPE'
      entityId: invoiceId,
      onMutations: () => ref.invalidate(invoiceDetailProvider(invoiceId)),
    ),
  ),
);
```

## Utilities (`shared/util/`)

**`LocalChatController`** — In-memory `ChatController` implementation for flutter_chat_ui. Manages message state locally without REST API persistence — the backend handles conversation state in the `ChatSession` record. Used by `RefinementChatSheet`.
```dart
final controller = LocalChatController();
await controller.insertMessage(TextMessage(id: 'msg-1', authorId: 'chef', ...));
// Pass to Chat widget: chatController: controller
```

**`formatDate(String?)`** — Formats ISO 8601 date as "MMM d, yyyy". Returns null for null input, raw string on parse failure.
```dart
formatDate('2026-04-15')  // → 'Apr 15, 2026'
```

**`formatCurrency(double)`** — Formats a number as US dollars with commas and cents.
```dart
formatCurrency(1234.5)  // → '\$1,234.50'
```

**`parseSseStream(ApiClient, String)`** — Parses a server-sent event stream from the given API path into `SseEvent` objects. Shared by invoice and recipe repositories.
```dart
await for (final event in parseSseStream(apiClient, '/api/invoices/ingest/stream')) {
  print('${event.event}: ${event.data}');
}
```

**`runTwoPhaseSync({...})`** — Orchestrates a two-phase SSE sync with a bottom-sheet progress display. Each phase is configured via `SyncPhaseConfig` (label, stream, event mappings). Returns a map of counter names to values for snackbar summary. Also exports `ActiveSyncItem` and `SyncProgressSheet`.
```dart
final counters = await runTwoPhaseSync(
  context: context,
  phase1: SyncPhaseConfig(
    label: 'Syncing',
    stream: repo.ingestStream,
    startEvent: 'downloading',
    successEvents: {'ingested': 'ingested'},
    ignoreEvents: {'skipped', 'error'},
  ),
  phase2: SyncPhaseConfig(
    label: 'Parsing',
    stream: repo.processStream,
    startEvent: 'processing',
    successEvents: {'processed': 'parsed'},
    ignoreEvents: {'failed'},
  ),
);
```

**`ApiClient`** ��� HTTP client that injects Firebase Bearer token on every request. Supports GET, POST, PUT, DELETE, and SSE streaming.
```dart
final response = await apiClient.get('/api/invoices');
final (:response, :client) = await apiClient.getStreaming('/api/invoices/ingest/stream');
```

## Providers (`shared/providers/`)

**`apiClientProvider`** — Singleton `ApiClient` instance.
**`chatRepositoryProvider`** — Singleton `ChatRepository` for refinement chat endpoints.
**`authServiceProvider`** — Singleton `FirebaseAuthService` instance.
**`authStateProvider`** — Streams the current Firebase `User`, null on sign-out.
**`isSignedInProvider`** — Convenience bool; true when a user is signed in.

## Repositories (`shared/repositories/`)

**`ChatRepository`** — Data access layer for refinement chat endpoints (`/api/chat/*`). Used by `RefinementChatSheet`.
```dart
final repo = ref.read(chatRepositoryProvider);
final session = await repo.startSession(domain: 'INVOICE', entityId: id);
final turn = await repo.sendMessage(sessionId: session.sessionId, message: 'Fix the butter');
```
