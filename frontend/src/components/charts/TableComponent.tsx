import { TableConfig } from '@/types/chart';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface TableComponentProps {
  config: TableConfig;
}

interface TableColumn {
  key: string;
  label: string;
  width?: string;
}

export function TableComponent({ config }: TableComponentProps) {
  const { data, columns } = config;

  // Auto-generate columns from first data row if not provided
  const tableColumns: TableColumn[] =
    columns ||
    (data.length > 0
      ? Object.keys(data[0]).map((key) => ({
          key,
          label: key.charAt(0).toUpperCase() + key.slice(1),
        }))
      : []);

  return (
    <div className="w-full rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {tableColumns.map((column) => (
              <TableHead key={column.key} style={column.width ? { width: column.width } : undefined}>
                {column.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={tableColumns.length}
                className="h-24 text-center text-muted-foreground"
              >
                No data available
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, rowIndex) => (
              <TableRow key={rowIndex}>
                {tableColumns.map((column) => (
                  <TableCell key={column.key}>
                    {formatCellValue(row[column.key])}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

/**
 * Format cell values for display
 */
function formatCellValue(value: any): string {
  if (value === null || value === undefined) {
    return '-';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    // Round to 2 decimal places for floats
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }
  return String(value);
}
