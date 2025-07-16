/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $VoiceTraceResponse = {
    properties: {
        transcript: {
            type: 'string',
            isRequired: true,
        },
        tasks_triggered: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
        memory_outputs: {
            type: 'array',
            contains: {
                type: 'dictionary',
                contains: {
                    properties: {
                    },
                },
            },
            isRequired: true,
        },
        executed_by: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
