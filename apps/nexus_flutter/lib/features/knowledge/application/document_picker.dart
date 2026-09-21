import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const maxDocumentBytes = 20 * 1024 * 1024;
typedef PickedDocument = ({String name, String mime, Uint8List bytes});

const _mimes = {
  'pdf': 'application/pdf',
  'txt': 'text/plain',
  'md': 'text/markdown',
  'docx':
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

final documentPickerProvider = Provider<Future<PickedDocument?> Function()>(
  (ref) => () async {
    final file = await openFile(
      acceptedTypeGroups: const [
        XTypeGroup(
          label: 'Documents',
          extensions: ['pdf', 'txt', 'md', 'docx'],
          uniformTypeIdentifiers: [
            'com.adobe.pdf',
            'public.plain-text',
            'public.text',
            'org.openxmlformats.wordprocessingml.document',
          ],
        ),
      ],
    );
    return file == null ? null : readPickedDocument(file);
  },
);

Future<PickedDocument> readPickedDocument(XFile file) async {
  final mime = _mimes[file.name.split('.').last.toLowerCase()];
  if (mime == null) throw const FormatException('Unsupported document format.');
  final length = await file.length();
  if (length > maxDocumentBytes) {
    throw const FormatException('Document exceeds 20 MiB.');
  }
  final builder = BytesBuilder(copy: false);
  await for (final chunk in file.openRead(0, length)) {
    builder.add(chunk);
    if (builder.length > maxDocumentBytes) {
      throw const FormatException('Document exceeds 20 MiB.');
    }
  }
  return (name: file.name, mime: mime, bytes: builder.takeBytes());
}
