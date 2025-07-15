/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $MemoryEntriesResponse = {
    properties: {
        entries: {
            type: 'array',
            contains: {
                type: 'MemoryEntry',
            },
            isRequired: true,
        },
    },
} as const;
