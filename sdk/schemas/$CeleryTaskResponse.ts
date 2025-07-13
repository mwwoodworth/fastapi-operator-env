/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CeleryTaskResponse = {
    description: `Response when a task is queued for Celery execution.`,
    properties: {
        task_id: {
            type: 'string',
            isRequired: true,
        },
    },
} as const;
