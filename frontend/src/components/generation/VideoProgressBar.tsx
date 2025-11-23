"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/trpc/react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { RefreshCw, X, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";

interface VideoProgressBarProps {
  userId: string;
}

export function VideoProgressBar({ userId }: VideoProgressBarProps) {
  const [showStopDialog, setShowStopDialog] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [websocketUrl, setWebsocketUrl] = useState<string | null>(null);
  const [lastStatus, setLastStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [isMounted, setIsMounted] = useState(true);

  // Validate userId
  const isValidUserId = !!userId && userId.trim().length > 0;

  // Poll checkProcessing every 5 seconds
  const checkProcessingQuery = api.script.checkProcessing.useQuery(undefined, {
    refetchInterval: 5000, // Poll every 5 seconds
    enabled: isValidUserId,
  });

  // Stop processing mutation
  const stopProcessingMutation = api.script.stopProcessing.useMutation({
    onSuccess: () => {
      if (!isMounted) return;
      setShowStopDialog(false);
      setSessionId(null);
      setWebsocketUrl(null);
      setLastStatus(null);
      setProgress(0);
      // Refetch to update status (only if query is enabled)
      // Use userId directly to avoid closure issues
      if (userId && userId.trim().length > 0) {
        void checkProcessingQuery.refetch();
      }
    },
  });

  // Handle component unmount
  useEffect(() => {
    return () => {
      setIsMounted(false);
    };
  }, []);

  // Connect to websocket if we have a sessionId
  // Note: useWebSocket constructs URL from sessionId, which should work with our backend
  const { isConnected, lastMessage } = useWebSocket(sessionId);

  // Update sessionId and websocketUrl when checkProcessing returns data
  useEffect(() => {
    if (checkProcessingQuery.data?.hasActiveProcess) {
      const newSessionId = checkProcessingQuery.data.sessionId ?? null;
      const newWebsocketUrl = checkProcessingQuery.data.websocketUrl ?? null;

      // Validate: if hasActiveProcess is true but sessionId is missing, treat as no active process
      if (!newSessionId) {
        // Invalid state - hasActiveProcess but no sessionId, clear state
        if (sessionId !== null) {
          setSessionId(null);
          setWebsocketUrl(null);
          setLastStatus(null);
          setProgress(0);
        }
        return;
      }

      // Only update if they changed to avoid reconnecting unnecessarily
      if (newSessionId !== sessionId) {
        setSessionId(newSessionId);
      }
      if (newWebsocketUrl !== websocketUrl) {
        setWebsocketUrl(newWebsocketUrl);
      }
    } else {
      // No active process - only clear if we had one before
      if (sessionId !== null) {
        setSessionId(null);
        setWebsocketUrl(null);
        setLastStatus(null);
        setProgress(0);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkProcessingQuery.data]);

  // Update progress and status from websocket messages
  useEffect(() => {
    let timeoutId: NodeJS.Timeout | undefined;
    
    if (lastMessage) {
      // Extract status from message
      const status = lastMessage.status || lastMessage.agentnumber || "processing";
      setLastStatus(status);

      // Extract progress if available
      if (lastMessage.progress) {
        if (typeof lastMessage.progress === "number") {
          setProgress(Math.min(100, Math.max(0, lastMessage.progress)));
        } else if (
          typeof lastMessage.progress === "object" &&
          "completed" in lastMessage.progress &&
          "total" in lastMessage.progress
        ) {
          const completed = lastMessage.progress.completed ?? 0;
          const total = lastMessage.progress.total ?? 1;
          // Prevent division by zero
          if (total > 0) {
            setProgress(Math.round((completed / total) * 100));
          } else {
            // If total is 0 or invalid, keep current progress
          }
        }
      } else {
        // If no progress info, keep current progress or set to indeterminate
        // Don't reset to 0 as that would hide the progress bar
      }

      // Check if process is complete or cancelled
      if (status === "finished" || status === "cancelled" || status === "error") {
        // Set progress to 100% for finished, 0% for cancelled/error
        if (status === "finished") {
          setProgress(100);
        }
        // Clear after a delay to show final status
        timeoutId = setTimeout(() => {
          if (isMounted) {
            setSessionId(null);
            setWebsocketUrl(null);
            setLastStatus(null);
            setProgress(0);
          }
        }, 5000);
      }
    }
    
    // Always return cleanup function to clear timeout if component unmounts or message changes
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [lastMessage, isMounted]);

  const handleRetry = useCallback(() => {
    void checkProcessingQuery.refetch();
  }, [checkProcessingQuery.refetch]);

  const handleStop = useCallback(() => {
    setShowStopDialog(true);
  }, []);

  const handleConfirmStop = useCallback(() => {
    stopProcessingMutation.mutate();
  }, [stopProcessingMutation]);

  // Don't render if userId is invalid
  if (!isValidUserId) {
    return null;
  }

  // Don't render if no active process (handle loading and error states)
  if (
    checkProcessingQuery.isLoading ||
    (!checkProcessingQuery.data?.hasActiveProcess && !sessionId)
  ) {
    return null;
  }
  
  // Show error state if query failed
  if (checkProcessingQuery.isError && !sessionId) {
    return null; // Silently fail - don't show error UI in sidebar
  }

  // Determine display status
  const displayStatus = lastStatus || (isConnected ? "processing" : "connecting");
  const isComplete = displayStatus === "finished";
  const isCancelled = displayStatus === "cancelled";
  const isError = displayStatus === "error";
  const isLoading = !isConnected && !lastStatus;

  return (
    <>
      <Card className="p-3 m-2">
        <div className="space-y-2">
          {/* Header with status */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              <span className="text-sm font-medium">
                {isComplete
                  ? "Video Complete"
                  : isCancelled
                    ? "Cancelled"
                    : isError
                      ? "Error"
                      : "Generating Video"}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRetry}
                disabled={checkProcessingQuery.isFetching}
                className="h-7 w-7 p-0"
              >
                <RefreshCw
                  className={`h-3 w-3 ${
                    checkProcessingQuery.isFetching ? "animate-spin" : ""
                  }`}
                />
              </Button>
              {!isComplete && !isCancelled && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleStop}
                  disabled={stopProcessingMutation.isPending}
                  className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>

          {/* Progress bar */}
          <Progress
            value={isComplete ? 100 : progress}
            className="h-2"
          />

          {/* Status text */}
          {lastMessage?.message && (
            <p className="text-xs text-muted-foreground truncate">
              {lastMessage.message}
            </p>
          )}
        </div>
      </Card>

      {/* Stop confirmation dialog */}
      <AlertDialog open={showStopDialog} onOpenChange={setShowStopDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Stop Video Generation?</AlertDialogTitle>
            <AlertDialogDescription>
              This will stop all active video generation processes for your
              account. Any progress will be lost and cannot be recovered.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmStop}
              disabled={stopProcessingMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {stopProcessingMutation.isPending ? "Stopping..." : "Stop"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}


