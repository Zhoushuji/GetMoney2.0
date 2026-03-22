import { create } from 'zustand';

type TaskState = {
  taskId?: string;
  setTaskId: (taskId?: string) => void;
};

export const useTaskStore = create<TaskState>((set) => ({
  taskId: undefined,
  setTaskId: (taskId) => set({ taskId }),
}));
