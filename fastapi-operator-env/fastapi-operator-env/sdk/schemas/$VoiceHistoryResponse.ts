/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $VoiceHistoryResponse = {
    properties: {
        entries: {
            type: 'array',
            contains: {
                type: 'VoiceHistoryEntry',
            },
            isRequired: true,
        },
    },
} as const;
