import { create } from 'zustand';

type TaskState = {
  taskId?: string;
  setTaskId: (taskId?: string) => void;
};

export const useTaskStore = create<TaskState>((set: (partial: Partial<TaskState>) => void) => ({
  taskId: undefined,
  setTaskId: (taskId?: string) => set({ taskId }),
}));
