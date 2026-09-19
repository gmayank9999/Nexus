import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/home/presentation/home_screen.dart';
import 'package:nexus_flutter/features/knowledge/presentation/knowledge_screen.dart';
import 'package:nexus_flutter/features/memory/presentation/memory_screen.dart';
import 'package:nexus_flutter/features/missions/presentation/mission_detail_screen.dart';
import 'package:nexus_flutter/features/missions/presentation/missions_screen.dart';
import 'package:nexus_flutter/features/outputs/presentation/outputs_screen.dart';
import 'package:nexus_flutter/features/placeholder/presentation/placeholder_screen.dart';
import 'package:nexus_flutter/routing/app_shell.dart';

final appRouter = GoRouter(
  initialLocation: '/home',
  routes: [
    GoRoute(
      path: '/tasks',
      builder: (context, state) => OutputsScreen(
        showTasks: true,
        runId: state.uri.queryParameters['run_id'],
      ),
    ),
    GoRoute(
      path: '/artifacts',
      builder: (context, state) => OutputsScreen(
        showTasks: false,
        runId: state.uri.queryParameters['run_id'],
      ),
    ),
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) =>
          AppShell(navigationShell: navigationShell),
      branches: [
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/home',
              builder: (context, state) => const HomeScreen(),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/missions',
              builder: (context, state) => const MissionsScreen(),
              routes: [
                GoRoute(
                  path: ':id',
                  builder: (context, state) =>
                      MissionDetailScreen(runId: state.pathParameters['id']!),
                ),
              ],
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/knowledge',
              builder: (context, state) => const KnowledgeScreen(),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/memory',
              builder: (context, state) => const MemoryScreen(),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/settings',
              builder: (context, state) => const PlaceholderScreen(
                title: 'Settings',
                icon: Icons.tune_outlined,
              ),
            ),
          ],
        ),
      ],
    ),
  ],
);
