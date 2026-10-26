import {
  ChunkConfigurationDescriptor,
  PageChunkStatistics,
} from './statistics.models';

export function chunkConfigurationLabel(
  configuration: ChunkConfigurationDescriptor,
): string {
  if (configuration.strategy === 'structural') {
    return 'Strukturális';
  }
  return `${configuration.max_tokens} / ${configuration.overlap_tokens} token`;
}

export function chunkConfigurationDescription(
  configuration: ChunkConfigurationDescriptor,
): string {
  if (configuration.strategy === 'structural') {
    return 'Dokumentumszerkezet-alapú feldolgozás, tokenes átfedés nélkül.';
  }
  return `Legfeljebb ${configuration.max_tokens} tokenes chunkok, ${configuration.overlap_tokens} token átfedéssel.`;
}

export function chunkStatusLabel(status: PageChunkStatistics['status']): string {
  return {
    complete: 'Teljes',
    partial: 'Részleges',
    missing: 'Hiányzik',
    invalid: 'Hibás',
    unverifiable: 'Nem ellenőrizhető',
  }[status];
}
