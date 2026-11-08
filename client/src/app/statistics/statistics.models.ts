export interface LengthDistribution {
  count: number;
  total: number;
  minimum: number | null;
  maximum: number | null;
  average: number | null;
  median: number | null;
  percentile_90: number | null;
  percentile_95: number | null;
}

export interface HistogramBucket {
  label: string;
  minimum: number;
  maximum: number;
  count: number;
}

export interface ChunkQualityStatistics {
  average_fill_percent: number | null;
  full_chunk_count: number | null;
  full_chunk_percent: number | null;
  short_chunk_count: number | null;
  short_chunk_percent: number | null;
  unique_token_count: number;
  stored_token_count: number;
  overlap_token_count: number;
  overlap_overhead_percent: number;
}

export interface ChunkValidationIssue {
  code: string;
  severity: 'warning' | 'error';
  message: string;
  line_number: number | null;
  affected_record_count: number;
}

export interface TextLengthStatistics {
  characters: LengthDistribution;
  words: LengthDistribution;
  tokens: LengthDistribution | null;
}

export interface ContentLengthStatistics {
  documents: TextLengthStatistics;
  complaints: TextLengthStatistics;
  inline_answers: TextLengthStatistics;
}

export interface ChunkConfigurationDescriptor {
  chunk_config_id: string;
  version: number | null;
  strategy: 'structural' | 'fixed_token';
  collection_name: string;
  tokenizer_model: string;
  tokenizer_revision: string;
  max_tokens: number | null;
  overlap_tokens: number;
}

export interface PageChunkStatistics {
  chunk_config_id: string;
  status: 'complete' | 'partial' | 'missing' | 'invalid' | 'unverifiable';
  document_count: number;
  chunk_count: number;
  missing_document_count: number | null;
  chunks_per_document?: LengthDistribution | null;
  chunks_per_document_histogram: HistogramBucket[];
  token_lengths: LengthDistribution;
  token_length_histogram: HistogramBucket[];
  quality: ChunkQualityStatistics;
  freshness_status: 'current' | 'stale' | 'unverifiable';
  validation_issues: ChunkValidationIssue[];
}

export interface DatasetChunkStatistics {
  chunk_config_id: string;
  status: 'complete' | 'partial' | 'missing' | 'invalid';
  page_count: number;
  complete_page_count: number;
  partial_page_count: number;
  missing_page_count: number;
  invalid_page_count: number;
  unverifiable_page_count: number;
  document_count: number;
  chunk_count: number;
  missing_document_count: number;
  chunks_per_document?: LengthDistribution;
  single_chunk_document_count: number;
  multi_chunk_document_count: number;
  outlier_documents: ChunkDocumentOutlier[];
  token_lengths: LengthDistribution;
  chunks_per_document_histogram: HistogramBucket[];
  token_length_histogram: HistogramBucket[];
  quality: ChunkQualityStatistics;
  validation_error_count: number;
  validation_warning_count: number;
  stale_page_count: number;
}

export interface ChunkDocumentOutlier {
  document_id: string;
  source_page: string;
  source_page_id: number | null;
  document_index: number;
  source_url: string;
  chunk_count: number;
  total_token_count: number;
}

export interface ContentCounts {
  document_count: number | null;
  complaint_document_count: number | null;
  complaint_message_count: number | null;
  inline_answer_count: number | null;
  external_answer_reference_count: number | null;
  detected_answer_count: number | null;
  answered_document_count: number | null;
}

export interface PageStatistics {
  page: string;
  page_id: number | null;
  source_url: string | null;
  downloaded_at: string | null;
  download_status: 'available' | 'missing' | 'invalid';
  processing_status: 'processed' | 'processed_empty' | 'not_processed' | 'invalid';
  content: ContentCounts;
  lengths: ContentLengthStatistics | null;
  chunk_statistics: PageChunkStatistics[];
}

export interface DatasetSummary {
  page_directory_count: number;
  downloaded_page_count: number;
  missing_source_metadata_count: number;
  invalid_source_metadata_count: number;
  processed_page_count: number;
  empty_processed_page_count: number;
  not_processed_page_count: number;
  invalid_documents_file_count: number;
  content: ContentCounts;
  lengths: ContentLengthStatistics;
  chunk_statistics: DatasetChunkStatistics[];
}

export interface StatisticsResponse {
  generated_at: string;
  statistics_schema_version: string;
  tokens_included: boolean;
  tokenizer: { model: string; revision: string } | null;
  chunk_configurations: ChunkConfigurationDescriptor[];
  dataset: {
    dataset_id: string;
    output_directory: string;
    exists: boolean;
    discovered_page_count: number;
    first_page_id: number | null;
    last_page_id: number | null;
    missing_page_ids_inside_range: number[];
  };
  summary: DatasetSummary;
  pages: PageStatistics[];
}
