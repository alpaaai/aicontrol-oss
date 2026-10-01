import { useEffect, useState } from "react";
import { listMcpServers, updateMcpServerStatus } from "@/api/mcpServers";
import type { McpServer, McpServerStatus } from "@/api/mcpServers";
import { EmptyState } from "@/components/primitives/EmptyState";
import { useAuth } from "@/hooks/useAuth";
import { RegisterMcpServerDialog } from "./RegisterMcpServerDialog";

const STATUS_STYLE: Record<McpServerStatus, string> = {
  active: "bg-ac-decision-allow-soft text-ac-decision-allow",
  pending_review: "bg-ac-surface-sunk text-ac-warning border border-ac-warning",
  blocked: "bg-ac-surface-sunk text-ac-decision-deny",
};

const STATUS_LABEL: Record<McpServerStatus, string> = {
  active: "Active",
  pending_review: "Pending review",
  blocked: "Blocked",
};

function McpServerRow({
  server,
  onChanged,
}: {
  server: McpServer;
  onChanged: () => void;
}) {
  const [confirmingBlock, setConfirmingBlock] = useState(false);
  const [updating, setUpdating] = useState(false);

  const setStatus = async (status: McpServerStatus) => {
    setUpdating(true);
    try {
      await updateMcpServerStatus(server.id, status);
      onChanged();
    } finally {
      setUpdating(false);
      setConfirmingBlock(false);
    }
  };

  return (
    <div
      data-testid={`mcp-server-row-${server.name}`}
      className="grid grid-cols-[1.4fr_1.4fr_1fr_1.4fr_1fr_1.2fr] items-start gap-4 px-4 py-3 border-b border-ac-hairline-soft"
    >
      <div className="min-w-0 text-body-md text-ac-body-strong truncate">
        {server.name}
      </div>
      <div className="min-w-0 text-identifier text-ac-muted truncate">
        {server.base_url}
      </div>
      <div className="min-w-0">
        <span
          className={`inline-flex items-center rounded-full px-[10px] py-[3px] text-label-uc ${STATUS_STYLE[server.status]}`}
        >
          {STATUS_LABEL[server.status]}
        </span>
      </div>
      <div className="min-w-0 text-body-sm text-ac-body truncate">
        {server.approved_tools.length > 0 ? server.approved_tools.join(", ") : "—"}
      </div>
      <div className="min-w-0 text-caption text-ac-muted">
        {server.created_at ? new Date(server.created_at).toLocaleDateString() : "—"}
      </div>
      <div className="min-w-0 flex items-center gap-2">
        {server.status === "pending_review" && (
          <button
            onClick={() => setStatus("active")}
            disabled={updating}
            className="text-caption text-ac-decision-allow hover:underline disabled:opacity-50"
          >
            Approve
          </button>
        )}
        {server.status !== "blocked" && !confirmingBlock && (
          <button
            onClick={() => setConfirmingBlock(true)}
            disabled={updating}
            className="text-caption text-ac-decision-deny hover:underline disabled:opacity-50"
          >
            Block
          </button>
        )}
        {confirmingBlock && (
          <span className="flex items-center gap-2 text-caption">
            <span className="text-ac-muted">Block this server?</span>
            <button
              onClick={() => setStatus("blocked")}
              disabled={updating}
              className="text-ac-decision-deny font-medium hover:underline disabled:opacity-50"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirmingBlock(false)}
              disabled={updating}
              className="text-ac-muted hover:underline disabled:opacity-50"
            >
              Cancel
            </button>
          </span>
        )}
      </div>
    </div>
  );
}

export function McpServersPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const refresh = () => {
    setLoading(true);
    setLoadError(false);
    return listMcpServers()
      .then(setServers)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-title-lg text-ac-ink">MCP Servers</h1>
        {isAdmin && (
          <button
            onClick={() => setDialogOpen(true)}
            className="bg-ac-primary text-white rounded-lg px-4 py-2 text-sm font-medium"
          >
            Register new MCP server
          </button>
        )}
      </div>

      <RegisterMcpServerDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onRegistered={refresh}
      />

      {loading ? (
        <div className="h-40 bg-ac-surface-sunk rounded-lg animate-pulse" />
      ) : loadError ? (
        <p className="text-body-sm text-ac-error py-8 text-center">
          Couldn't load MCP servers. Try refreshing the page.
        </p>
      ) : servers.length === 0 ? (
        <EmptyState
          title={`No MCP servers registered yet${isAdmin ? " — use the Register new MCP server button above" : ""}.`}
        />
      ) : (
        <div
          data-testid="mcp-servers-table"
          className="border border-ac-hairline rounded-lg bg-ac-surface-card overflow-y-auto max-h-[70vh]"
        >
          <div className="grid grid-cols-[1.4fr_1.4fr_1fr_1.4fr_1fr_1.2fr] gap-4 px-4 py-2.5 text-label-uc text-ac-muted border-b border-ac-hairline bg-ac-surface-sunk">
            <div>Name</div>
            <div>Base URL</div>
            <div>Status</div>
            <div>Approved tools</div>
            <div>Created</div>
            <div>Actions</div>
          </div>
          {servers.map((s) => (
            <McpServerRow key={s.id} server={s} onChanged={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}
