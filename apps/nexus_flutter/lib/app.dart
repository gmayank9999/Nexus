import 'package:flutter/material.dart';
import 'package:nexus_flutter/routing/app_router.dart';
import 'package:nexus_flutter/theme/nexus_theme.dart';

class NexusApp extends StatelessWidget {
  const NexusApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'NEXUS',
      debugShowCheckedModeBanner: false,
      theme: NexusTheme.dark,
      routerConfig: appRouter,
    );
  }
}
