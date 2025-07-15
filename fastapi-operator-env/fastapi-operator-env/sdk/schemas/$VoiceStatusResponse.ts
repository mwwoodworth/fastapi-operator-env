/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $VoiceStatusResponse = {
    properties: {
        latest_transcript: {
            type: 'string',
            isRequired: true,
        },
        task_executed: {
            type: 'boolean',
            isRequired: true,
        },
        memory_link: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
            isRequired: true,
        },
        execution_status: {
            type: 'string',
            isRequired: true,
        },
        processed_by: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
